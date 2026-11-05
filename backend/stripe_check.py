import stripe
from app.core.config import settings

stripe.api_key=settings.stripe_secret_key
price=stripe.Price.retrieve(settings.stripe_price_id,expand=["product"])

print("Product :", price.product.name)
print("Amount  :", price.unit_amount / 100, price.currency.upper())
print("Interval:", price.recurring.interval)