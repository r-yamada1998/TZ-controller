from __future__ import annotations

from .configuration import Config
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Union,
)
import abc
import atexit
import fcntl
import logging
import os
import threading
from pathlib import Path


class DeviceLockError(RuntimeError):
    """Raised when the device lock is already held by another process."""
    pass


class DeviceBase(abc.ABC):
    """
    Base class for device controllers.

    Singleton policy:
        One instance per (class, device_name, identity)

    Process exclusion policy:
        One running process per lock file path.
        By default, the lock file name is based on both device_name and identity.
    """

    Model: ClassVar[str]
    Manufacturer: ClassVar[str]
    Identifier: ClassVar[Optional[str]] = None
    Config: ClassVar[Union[Config, None]] = None

    _instances: ClassVar[Dict[tuple[type, str, Any], "DeviceBase"]] = {}
    _instances_lock: ClassVar[threading.Lock] = threading.Lock()
    _implementations: ClassVar[List[Type["DeviceBase"]]] = []
    _kind: ClassVar[Type["DeviceBase"]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        if hasattr(cls, "Model"):
            cls._implementations.append(cls)

        if cls.__base__ is DeviceBase:
            cls._kind = cls

    def __new__(
        cls,
        device_name: str,
        config_file: str,
        lock_dir: str = "/tmp",
    ) -> "DeviceBase":
        if cls is DeviceBase or not hasattr(cls, "Model"):
            raise TypeError("DeviceBase or abstract subclass cannot be instantiated.")

        config = Config.load_config(path=config_file)

        try:
            device_cfg = config[device_name]
        except Exception as e:
            raise KeyError(f"device_name={device_name!r} is not found in config.") from e

        identity = cls._identity(device_cfg, cls.Identifier)
        key = (cls, device_name, identity)

        with cls._instances_lock:
            if key not in cls._instances:
                inst = super().__new__(cls)
                inst._init_done = False
                cls._instances[key] = inst

        return cls._instances[key]

    def __init__(
        self,
        device_name: str,
        config_file: str,
        lock_dir: str = "/tmp",
    ) -> None:
        if getattr(self, "_init_done", False):
            self._validate_reinit_args(
                device_name=device_name,
                config_file=config_file,
                lock_dir=lock_dir,
            )
            return

        self.device_name = device_name
        self.config_file = config_file
        self.lock_dir = Path(lock_dir)

        self.config = Config.load_config(path=config_file)

        try:
            self.device_config = self.config[device_name]
        except Exception as e:
            raise KeyError(f"device_name={device_name!r} is not found in config.") from e

        self.identity = self._identity(self.device_config, self.Identifier)
        self.lock_file_path = self._build_lock_file_path()
        self._lock_fd = None

        self.logger = logging.getLogger(self._build_logger_name())

        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )

        self._init_done = True

    @staticmethod
    def _identity(
        cfg: Union[Config, None],
        identifier: Optional[str] = None,
    ) -> Any:
        """
        Resolve identity from config using `identifier`.

        If identifier is None, identity becomes None.
        """
        if identifier is None:
            return None
        return getattr(cfg, identifier, None)

    def _validate_reinit_args(
        self,
        device_name: str,
        config_file: str,
        lock_dir: str,
    ) -> None:
        """
        Guard against accidental re-initialization with inconsistent arguments.
        """
        if self.device_name != device_name:
            raise ValueError(
                f"This instance is already bound to device_name={self.device_name!r}, "
                f"but got {device_name!r}."
            )

        if self.config_file != config_file:
            raise ValueError(
                f"{self.__class__.__name__}({device_name!r}) is already initialized "
                f"with config_file={self.config_file!r}, but got {config_file!r}."
            )

        if self.lock_dir != Path(lock_dir):
            raise ValueError(
                f"{self.__class__.__name__}({device_name!r}) is already initialized "
                f"with lock_dir={str(self.lock_dir)!r}, but got {lock_dir!r}."
            )

    def _build_logger_name(self) -> str:
        identity_part = "none" if self.identity is None else str(self.identity)
        return f"{self.__class__.__name__}.{self.device_name}.{identity_part}"

    def _build_lock_file_path(self) -> Path:
        """
        Build lock file path.

        Since singleton is separated by (device_name, identity), the lock file should
        also be separated by them. Otherwise, different identities under the same
        device_name would incorrectly block each other.
        """
        identity_part = "none" if self.identity is None else str(self.identity)
        safe_identity = str(identity_part).replace("/", "_")
        safe_device_name = str(self.device_name).replace("/", "_")
        filename = f"{safe_device_name}__{safe_identity}.lock"
        return self.lock_dir / filename

    def acquire_lock(self) -> None:
        """
        Acquire a non-blocking exclusive lock.

        Raises:
            DeviceLockError:
                If another process is already running with the same lock target.
        """
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._lock_fd = open(self.lock_file_path, "w")

        try:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            self._lock_fd.close()
            self._lock_fd = None
            raise DeviceLockError(
                f"{self.device_name!r} (identity={self.identity!r}) is already running."
            ) from e

        self._lock_fd.seek(0)
        self._lock_fd.truncate()
        self._lock_fd.write(str(os.getpid()))
        self._lock_fd.flush()

        atexit.register(self.release_lock)
        self.logger.info("Lock acquired: %s", self.lock_file_path)

    def release_lock(self) -> None:
        if self._lock_fd is None:
            return

        try:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
            self._lock_fd.close()
        except Exception:
            pass
        finally:
            self._lock_fd = None

        self.logger.info("Lock released: %s", self.lock_file_path)

    def start(self, **kwargs) -> None:
        """
        Common startup flow.
        """
        self.acquire_lock()
        try:
            self.setup()
            self.run(**kwargs)
        finally:
            try:
                self.teardown()
            finally:
                self.release_lock()

    def setup(self) -> None:
        """
        Override in subclasses if needed.
        """
        pass

    @abc.abstractmethod
    def run(self, **kwargs) -> None:
        """
        Device-specific main routine.
        """
        raise NotImplementedError

    def teardown(self) -> None:
        """
        Override in subclasses if needed.
        """
        pass