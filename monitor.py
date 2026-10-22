import json, os, time, urllib.request, urllib.parse, pathlib, hashlib, html
from datetime import datetime,timezone
WALLET=os.environ.get("SOURCE_WALLET","0xb31e41965df4ab8014de4c4d8da9deff0a6ac120").lower()
P=pathlib.Path("state.json")
NOW=int(time.time())
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"c63amg-paper-tracker/1.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
def trades(since):
 # v2 activity captures wallet-side fills, including maker executions.
 # v1 /trades is legacy and by default reports taker trades only.
 results=[]; cursor=None
 for _ in range(5):
  params={"user":WALLET,"type":"TRADE","limit":1000,"start":max(1,int(since)-120),"sort_direction":"DESC"}
  if cursor: params["cursor"]=cursor
  response=fetch("https://data-api.polymarket.com/v2/activity?"+urllib.parse.urlencode(params))
  if not isinstance(response,dict) or not isinstance(response.get("data"),list):
   raise RuntimeError("Unexpected Polymarket v2 activity response")
  for x in response["data"]:
   if x.get("type")!="TRADE" or x.get("is_combo"):continue
   results.append({
    "proxyWallet":x.get("proxy_wallet",x.get("proxyWallet",WALLET)),
    "transactionHash":x.get("transaction_hash",x.get("transactionHash","")),
    "asset":x.get("token_id",x.get("asset","")),
    "conditionId":x.get("condition_id",x.get("conditionId","")),
    "timestamp":x.get("timestamp",0),
    "side":x.get("side",""),
    "price":x.get("price",0),
    "size":x.get("size",0),
    "title":x.get("title",""),
    "outcome":x.get("outcome",""),
   })
  cursor=(response.get("pagination") or {}).get("next_cursor")
  if not cursor: break
 if cursor:
  raise RuntimeError("Activity feed exceeds 5000 items; refusing incomplete scan")
 return sorted(results,key=lambda t:int(t.get("timestamp",0)))
def book(token):
 v=fetch("https://clob.polymarket.com/book?"+urllib.parse.urlencode({"token_id":token}))
 return sorted([(float(x["price"]),float(x["size"])) for x in v.get("asks",[]) if float(x["size"])>0]),sorted([(float(x["price"]),float(x["size"])) for x in v.get("bids",[]) if float(x["size"])>0],reverse=True)
def key(t):
 return hashlib.sha256("|".join(str(t.get(k,"")) for k in ("proxyWallet","transactionHash","asset","side","timestamp","price","size")).encode()).hexdigest()
def init():
 return {"started":NOW,"end":NOW+604800,"updated":NOW,"cash":1000.0,"realized":0.0,"positions":{},"seen":[],"events":[],"copied":0,"skipped":0}
def apply(s,t):
 src=float(t.get("price") or 0); size=float(t.get("size") or 0); token=str(t.get("asset",""))
 side=str(t.get("side","")).upper(); ts=int(t.get("timestamp") or 0)
 e={"ts":ts,"detected":NOW,"side":side,"market":str(t.get("title",""))[:140],"outcome":str(t.get("outcome",""))[:60],"price":src,"decision":"SKIPPED","reason":""}
 def skip(reason):e["reason"]=reason;s["skipped"]+=1
 if ts<=0 or NOW-ts>420 or ts>NOW+5:skip("late_or_invalid")
 elif not token or side not in ("BUY","SELL") or not (0<src<1) or size<=0:skip("bad_signal")
 elif side=="BUY" and (src>=.99 or src<.02):skip("price_filter")
 else:
  p=s["positions"].get(token)
  if side=="SELL" and (not p or p["qty"]<=0):skip("no_inventory")
  else:
   buys=sum(x.get("spent",0) for x in s["events"] if x.get("side")=="BUY" and x["decision"]=="COPIED" and x.get("detected",0)//86400==NOW//86400)
   exposure=sum(z["cost"] for z in s["positions"].values())
   mcost=sum(z["cost"] for z in s["positions"].values() if z["condition"]==str(t.get("conditionId","")))
   budget=min(10,s["cash"],150-buys,500-exposure,50-mcost)
   if side=="BUY" and budget<1:skip("risk_limit")
   else:
    try:
     asks,bids=book(token)
     levels=asks if side=="BUY" else bids
     if not levels:skip("no_depth")
     elif (side=="BUY" and levels[0][0]>min(.989999,src+.01)) or (side=="SELL" and levels[0][0]<src-.01):skip("price_moved")
     else:
      available=budget if side=="BUY" else min(size,p["qty"]); qty=0.; cash=0.
      for price,depth in levels:
       if (side=="BUY" and price>min(.989999,src+.01)) or (side=="SELL" and price<src-.01):break
       n=min(depth,(available-cash)/(price*1.002)) if side=="BUY" else min(depth,available-qty)
       if n<=1e-9:break
       qty+=n;cash+=n*price*(1.002 if side=="BUY" else .998)
       if (side=="BUY" and cash>=available-.0001) or (side=="SELL" and qty>=available-.0001):break
      if qty<=1e-8:skip("no_fill")
      elif side=="BUY":
       s["cash"]-=cash
       if not p:p={"qty":0.,"cost":0.,"condition":str(t.get("conditionId","")),"title":e["market"],"outcome":e["outcome"]};s["positions"][token]=p
       p["qty"]+=qty;p["cost"]+=cash
       e.update({"decision":"COPIED","reason":"paper_buy","spent":cash,"qty":qty,"sim_price":cash/(qty*1.002)});s["copied"]+=1
      else:
       basis=p["cost"]*qty/p["qty"];p["qty"]-=qty;p["cost"]-=basis
       s["cash"]+=cash;s["realized"]+=cash-basis
       e.update({"decision":"COPIED","reason":"paper_sell","proceeds":cash,"qty":qty,"sim_price":cash/(qty*.998)});s["copied"]+=1
    except Exception as exc:skip("orderbook_error:"+type(exc).__name__)
 s["events"].append(e);s["events"]=s["events"][-250:]
 return e
def run():
 s=json.loads(P.read_text()) if P.exists() else init()
 # Polymarket activity may be indexed late; use a rolling overlap and dedupe by fill key.
 # Catch up after GitHub schedule delays instead of advancing the API window blindly.
 previous=int(s.get("updated",s.get("started",NOW)))
 lookback=max(1,min(previous-7200,NOW-21600))
 rows=trades(lookback); seen=set(s["seen"]); newly=[]; alerts=[]
 s["poll_from_ts"]=lookback
 s["feed_version"]="v2_activity"
 s["polling_gap_s"]=max(0,NOW-previous)
 s["feed_status"]="live"
 s["feed_rows"]=len(rows)
 s["feed_latest_ts"]=max((int(t.get("timestamp",0)) for t in rows),default=0)
 # One lightweight 24h feed diagnostic to distinguish no fresh fills from a broken source.
 diagnostic=fetch("https://data-api.polymarket.com/v2/activity?"+urllib.parse.urlencode({"user":WALLET,"type":"TRADE","limit":10,"start":max(1,NOW-86400)}))
 if not isinstance(diagnostic,dict) or not isinstance(diagnostic.get("data"),list):
  raise RuntimeError("Malformed v2 source diagnostics")
 sample=diagnostic["data"]
 s["source_24h_sample_count"]=len(sample)
 s["source_latest_known_ts"]=max((int(v.get("timestamp") or 0) for v in sample),default=0)
 s["source_latest_markets"]=[str(v.get("title") or "")[:80] for v in sample[:3]]
 print("v2 source recent rows:",len(rows),"recent latest:",s["feed_latest_ts"],"24h sample:",len(sample),"sample latest:",s["source_latest_known_ts"])
 for t in rows:
  k=key(t)
  # Trades before our paper experiment began are history, not new signals.
  ts=int(t.get("timestamp") or 0)
  if k not in seen and ts>=int(s["started"])-10:
   newly.append((k,t))
 if not P.exists():
  s["seen"]=[key(t) for t in rows];s["events"]=[] # No historical trades on first run
 elif NOW<s["end"]:
  for k,t in newly:
   alerts.append(apply(s,t))
  s["seen"]=list(dict.fromkeys((s["seen"]+[k for k,t in newly])))[-3500:]
 s["new_detected"]=len(newly)
 s["updated"]=NOW
 pathlib.Path(".alerts.json").write_text(json.dumps({"generated_at":NOW,"events":alerts},ensure_ascii=False))
 P.write_text(json.dumps(s,ensure_ascii=False,indent=2))
 pathlib.Path("site").mkdir(exist_ok=True)
 pathlib.Path("site/state.json").write_text(json.dumps(s,ensure_ascii=False))
 print("Copied:",s["copied"],"Skipped:",s["skipped"],"Updated:",NOW)
if __name__=="__main__":run()
