# -*- coding: utf-8 -*-
import scrapy


class YahoofinanceSpider(scrapy.Spider):
    name = 'yahoofinance'
    allowed_domains = ['finance.yahoo.com']
    start_urls = ['https://finance.yahoo.com/quote/AAPL/options?']

    def parse(self, response):
        pass
