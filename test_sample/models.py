from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Entity:
    id: int
    created_at: str


@dataclass
class User(Entity):
    username: str
    email: str
    password_hash: str
    is_active: bool = True
    
    def validate_password(self, password: str) -> bool:
        return self.password_hash == hash(password)
    
    def deactivate(self) -> None:
        self.is_active = False


@dataclass
class Product(Entity):
    name: str
    description: str
    price: float
    stock: int = 0
    category: Optional[str] = None
    
    def is_in_stock(self) -> bool:
        return self.stock > 0
    
    def update_stock(self, quantity: int) -> None:
        self.stock += quantity


@dataclass
class OrderItem:
    product: Product
    quantity: int
    unit_price: float
    
    def total_price(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order(Entity):
    user: User
    items: List[OrderItem] = field(default_factory=list)
    status: str = "pending"
    
    def add_item(self, product: Product, quantity: int) -> None:
        item = OrderItem(product=product, quantity=quantity, unit_price=product.price)
        self.items.append(item)
    
    def calculate_total(self) -> float:
        return sum(item.total_price() for item in self.items)
    
    def complete(self) -> None:
        self.status = "completed"
