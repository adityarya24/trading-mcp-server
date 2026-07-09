import yfinance as yf

t = yf.Ticker("^NSEI")
print("options", t.options[:3] if t.options else None)
if t.options:
    chain = t.option_chain(t.options[0])
    print("calls", len(chain.calls), "puts", len(chain.puts))
    print(chain.calls.head(2))

for sym in ["^CNXPHARMA", "^CNXAUTO", "^CNXFMCG", "^CNXMETAL", "^CNXENERGY", "NIFTY PHARMA"]:
    q = yf.Ticker(sym if sym.startswith("^") else "^CNXIT")
    if sym == "NIFTY PHARMA":
        from market.providers.yahoo import YahooFinanceProvider
        p = YahooFinanceProvider()
        print(sym, p.validate_symbol(sym))
    else:
        i = yf.Ticker(sym).info
        print(sym, i.get("regularMarketPrice"), i.get("regularMarketChangePercent"))