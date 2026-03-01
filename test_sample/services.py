from __future__ import annotations
from typing import List, Optional

from .models import User, Product, Order, OrderItem


class Database:
    def __init__(self):
        self._users: List[User] = []
        self._products: List[Product] = []
        self._orders: List[Order] = []
        self._next_id = 1
    
    def _get_next_id(self) -> int:
        id_val = self._next_id
        self._next_id += 1
        return id_val
    
    def save_user(self, user: User) -> User:
        user.id = self._get_next_id()
        self._users.append(user)
        return user
    
    def find_user_by_email(self, email: str) -> Optional[User]:
        for user in self._users:
            if user.email == email:
                return user
        return None
    
    def save_product(self, product: Product) -> Product:
        product.id = self._get_next_id()
        self._products.append(product)
        return product
    
    def find_product_by_id(self, product_id: int) -> Optional[Product]:
        for product in self._products:
            if product.id == product_id:
                return product
        return None
    
    def save_order(self, order: Order) -> Order:
        order.id = self._get_next_id()
        self._orders.append(order)
        return order


class UserService:
    def __init__(self, db: Database):
        self._db = db
    
    def register(self, username: str, email: str, password: str) -> User:
        existing = self._db.find_user_by_email(email)
        if existing:
            raise ValueError(f"User with email {email} already exists")
        
        user = User(
            id=0,
            created_at="now",
            username=username,
            email=email,
            password_hash=str(hash(password)),
        )
        return self._db.save_user(user)
    
    def authenticate(self, email: str, password: str) -> Optional[User]:
        user = self._db.find_user_by_email(email)
        if user and user.validate_password(password):
            return user
        return None


class ProductService:
    def __init__(self, db: Database):
        self._db = db
    
    def create_product(self, name: str, description: str, price: float, stock: int = 0) -> Product:
        product = Product(
            id=0,
            created_at="now",
            name=name,
            description=description,
            price=price,
            stock=stock,
        )
        return self._db.save_product(product)
    
    def get_product(self, product_id: int) -> Optional[Product]:
        return self._db.find_product_by_id(product_id)
    
    def update_stock(self, product_id: int, quantity: int) -> bool:
        product = self._db.find_product_by_id(product_id)
        if product:
            product.update_stock(quantity)
            return True
        return False


class OrderService:
    def __init__(self, db: Database, product_service: ProductService):
        self._db = db
        self._product_service = product_service
    
    def create_order(self, user: User) -> Order:
        order = Order(
            id=0,
            created_at="now",
            user=user,
        )
        return self._db.save_order(order)
    
    def add_to_order(self, order: Order, product_id: int, quantity: int) -> bool:
        product = self._product_service.get_product(product_id)
        if product and product.is_in_stock():
            order.add_item(product, quantity)
            return True
        return False
    
    def checkout(self, order: Order) -> float:
        total = order.calculate_total()
        order.complete()
        return total
