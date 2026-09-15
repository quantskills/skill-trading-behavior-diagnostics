from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    p=argparse.ArgumentParser(); p.add_argument("--directory",default="data"); p.add_argument("--seed",type=int,default=9); a=p.parse_args(); rng=np.random.default_rng(a.seed); out=Path(a.directory); out.mkdir(parents=True,exist_ok=True)
    trades=[]; market=[]; dates=pd.bdate_range("2024-01-02",periods=180); symbols=["000001.SZ","600000.SH","000333.SZ"]
    prices={s:10+i*5 for i,s in enumerate(symbols)}
    for d in dates:
        for s in symbols:
            ret=float(rng.normal(.0002,.015)); prices[s]*=1+ret; market.append((d,s,ret))
    for i in range(36):
        s=symbols[i%3]; open_i=i*4; hold=2 if i%2==0 else 12; base=next(x[2] for x in market if x[0]==dates[open_i] and x[1]==s); price=10*(1+base); win=i%2==0
        trades.append((dates[open_i],s,"买入",100,price,5)); trades.append((dates[min(open_i+hold,len(dates)-1)],s,"卖出",100,price*(1.08 if win else .9),5))
    pd.DataFrame(trades,columns=["成交时间","证券代码","买卖方向","成交数量","成交价格","手续费"]).to_csv(out/"tonghuashun_demo.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(market,columns=["date","symbol","return"]).to_csv(out/"market_returns.csv",index=False)
    print(out)
if __name__=="__main__": main()
