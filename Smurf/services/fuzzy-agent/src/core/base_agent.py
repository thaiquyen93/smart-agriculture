from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

class BaseAgent(ABC):
    """
    Abstract Base Class cho tất cả các Agent trong hệ thống Multi-Agent.
    Mọi Agent đều phải thực thi phương thức `process()`.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Xử lý dữ liệu đầu vào và trả về kết quả.
        
        Args:
            data (Dict[str, Any]): Dữ liệu đầu vào.
            
        Returns:
            Dict[str, Any]: Kết quả xử lý.
        """
        pass
