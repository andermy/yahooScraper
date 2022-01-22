# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class Option(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    contract_name = scrapy.Field()
    last_trade_date = scrapy.Field()
    today = scrapy.Field()
    strike_date = scrapy.Field()
    strike = scrapy.Field()
    last_price = scrapy.Field()
    bid = scrapy.Field()
    ask = scrapy.Field()
    volume = scrapy.Field()
    open_interest = scrapy.Field()
    implied_volatility = scrapy.Field()
    option_type = scrapy.Field()
    pass
