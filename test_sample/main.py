from .models import User, Product, Order
from .services import Database, UserService, ProductService, OrderService


def run_demo():
    db = Database()
    user_service = UserService(db)
    product_service = ProductService(db)
    order_service = OrderService(db, product_service)
    
    user = user_service.register("john_doe", "john@example.com", "secret123")
    print(f"Created user: {user.username}")
    
    laptop = product_service.create_product(
        name="Laptop",
        description="High-performance laptop",
        price=999.99,
        stock=10,
    )
    print(f"Created product: {laptop.name}")
    
    order = order_service.create_order(user)
    order_service.add_to_order(order, laptop.id, 2)
    total = order_service.checkout(order)
    print(f"Order completed! Total: ${total:.2f}")


if __name__ == "__main__":
    run_demo()
