from enum import StrEnum

class Brand(StrEnum):
    SMA = "sma"
    TEST = "test"

brand = Brand("sma")
print(brand == Brand.SMA)