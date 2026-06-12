//+------------------------------------------------------------------+
//| ThangRodBridgeEA.mq5                                             |
//| Outbound TCP client for the ทางรอด backend.                      |
//+------------------------------------------------------------------+
#property strict
#property version   "0.30"
#property description "Add BackendHost to Tools > Options > Expert Advisors > allowed addresses."

#include <Trade/Trade.mqh>

input string BackendHost       = "127.0.0.1";
input int    BackendPort       = 5555;
input string BackendSharedSecret = "";
input int    ConnectTimeoutMs  = 3000;
input bool   AllowExecution    = false;
input bool   AllowRealTrading  = false;
input ulong  ExpertMagicNumber = 260611;
input bool   PersistIdempotency = true;
input int    IdempotencyCacheMax = 1000;

CTrade trade;
int socket_handle = INVALID_HANDLE;
string receive_buffer = "";
string stored_keys[];
string stored_results[];

string JsonEscape(string value)
  {
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r","\\r");
   StringReplace(value,"\n","\\n");
   return value;
  }

int JsonValueStart(const string json,const string key)
  {
   string marker="\""+key+"\"";
   int pos=StringFind(json,marker);
   if(pos<0)
      return -1;
   pos=StringFind(json,":",pos+StringLen(marker));
   if(pos<0)
      return -1;
   pos++;
   while(pos<StringLen(json) && StringGetCharacter(json,pos)<=32)
      pos++;
   return pos;
  }

string JsonString(const string json,const string key,const string fallback="")
  {
   int pos=JsonValueStart(json,key);
   if(pos<0 || StringSubstr(json,pos,1)!="\"")
      return fallback;
   pos++;
   string result="";
   bool escaped=false;
   for(int i=pos;i<StringLen(json);i++)
     {
      string ch=StringSubstr(json,i,1);
      if(escaped)
        {
         if(ch=="n") result+="\n";
         else if(ch=="r") result+="\r";
         else result+=ch;
         escaped=false;
        }
      else if(ch=="\\")
         escaped=true;
      else if(ch=="\"")
         return result;
      else
         result+=ch;
     }
   return fallback;
  }

double JsonDouble(const string json,const string key,const double fallback=0.0)
  {
   int pos=JsonValueStart(json,key);
   if(pos<0)
      return fallback;
   int end=pos;
   while(end<StringLen(json))
     {
      ushort ch=(ushort)StringGetCharacter(json,end);
      if((ch>='0' && ch<='9') || ch=='-' || ch=='+' || ch=='.' || ch=='e' || ch=='E')
         end++;
      else
         break;
     }
   return StringToDouble(StringSubstr(json,pos,end-pos));
  }

string JsonNumber(const double value,const int digits=8)
  {
   return DoubleToString(value,digits);
  }

bool SendLine(const string line)
  {
   if(socket_handle==INVALID_HANDLE || !SocketIsConnected(socket_handle))
      return false;
   char bytes[];
   int length=StringToCharArray(line+"\n",bytes)-1;
   return length>0 && SocketSend(socket_handle,bytes,length)==length;
  }

void SendResult(const string id,const string result)
  {
   SendLine("{\"id\":\""+JsonEscape(id)+"\",\"result\":"+result+"}");
  }

void SendError(const string id,const string error)
  {
   SendLine("{\"id\":\""+JsonEscape(id)+"\",\"error\":\""+JsonEscape(error)+"\"}");
  }

bool EnsureConnected()
  {
   if(socket_handle!=INVALID_HANDLE && SocketIsConnected(socket_handle))
      return true;
   if(socket_handle!=INVALID_HANDLE)
      SocketClose(socket_handle);
   socket_handle=SocketCreate(SOCKET_DEFAULT);
   if(socket_handle==INVALID_HANDLE)
     {
      Print("SocketCreate failed: ",GetLastError());
      return false;
     }
   if(!SocketConnect(socket_handle,BackendHost,(uint)BackendPort,(uint)ConnectTimeoutMs))
     {
      PrintFormat("Connection to %s:%d failed: %d",BackendHost,BackendPort,GetLastError());
      SocketClose(socket_handle);
      socket_handle=INVALID_HANDLE;
      return false;
     }
   SocketTimeouts(socket_handle,(uint)ConnectTimeoutMs,(uint)ConnectTimeoutMs);
   if(BackendSharedSecret=="" ||
      !SendLine("{\"type\":\"auth\",\"secret\":\""+JsonEscape(BackendSharedSecret)+"\"}"))
     {
      Print("EA authentication handshake failed; configure BackendSharedSecret");
      SocketClose(socket_handle);
      socket_handle=INVALID_HANDLE;
      return false;
     }
   PrintFormat("Connected to ทางรอด backend at %s:%d",BackendHost,BackendPort);
   return true;
  }

string AccountTypeName()
  {
   ENUM_ACCOUNT_TRADE_MODE mode=(ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode==ACCOUNT_TRADE_MODE_DEMO) return "DEMO";
   if(mode==ACCOUNT_TRADE_MODE_REAL) return "REAL";
   return "UNKNOWN";
  }

string HealthResult()
  {
   string detail=AllowExecution ? "EA connected; execution enabled" : "EA connected; execution disabled";
   return "{\"ok\":true,\"detail\":\""+JsonEscape(detail)+"\",\"server_time_epoch\":"+
          IntegerToString((long)TimeGMT())+"}";
  }

string AccountResult()
  {
   return "{"
          "\"account_type\":\""+AccountTypeName()+"\","
          "\"login\":"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+","
          "\"server\":\""+JsonEscape(AccountInfoString(ACCOUNT_SERVER))+"\","
          "\"currency\":\""+JsonEscape(AccountInfoString(ACCOUNT_CURRENCY))+"\","
          "\"balance\":"+JsonNumber(AccountInfoDouble(ACCOUNT_BALANCE))+","
          "\"equity\":"+JsonNumber(AccountInfoDouble(ACCOUNT_EQUITY))+","
          "\"margin\":"+JsonNumber(AccountInfoDouble(ACCOUNT_MARGIN))+","
          "\"free_margin\":"+JsonNumber(AccountInfoDouble(ACCOUNT_MARGIN_FREE))+","
          "\"leverage\":"+IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE))+
          "}";
  }

string QuoteResult(const string symbol)
  {
   MqlTick tick;
   if(!SymbolInfoTick(symbol,tick))
      return "";
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   double spread=(point>0.0 ? (tick.ask-tick.bid)/point : 0.0);
   return "{"
          "\"bid\":"+JsonNumber(tick.bid)+","
          "\"ask\":"+JsonNumber(tick.ask)+","
          "\"spread_points\":"+JsonNumber(spread,2)+","
          "\"time_epoch\":"+IntegerToString((long)tick.time)+
          "}";
  }

string SymbolInfoResult(const string symbol)
  {
   return "{"
          "\"tick_size\":"+JsonNumber(SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_SIZE))+","
          "\"tick_value\":"+JsonNumber(SymbolInfoDouble(symbol,SYMBOL_TRADE_TICK_VALUE))+","
          "\"volume_min\":"+JsonNumber(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN))+","
          "\"volume_max\":"+JsonNumber(SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX))+","
          "\"volume_step\":"+JsonNumber(SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP))+
          "}";
  }

string PositionsResult()
  {
   string items="";
   int total=PositionsTotal();
   for(int i=0;i<total;i++)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0)
         continue;
      string symbol=PositionGetString(POSITION_SYMBOL);
      long type=PositionGetInteger(POSITION_TYPE);
      string side=(type==POSITION_TYPE_BUY ? "BUY" : "SELL");
      if(items!="") items+=",";
      items+="{"
             "\"ticket\":"+IntegerToString((long)ticket)+","
             "\"symbol\":\""+JsonEscape(symbol)+"\","
             "\"side\":\""+side+"\","
             "\"volume\":"+JsonNumber(PositionGetDouble(POSITION_VOLUME))+","
             "\"open_price\":"+JsonNumber(PositionGetDouble(POSITION_PRICE_OPEN))+","
             "\"sl\":"+JsonNumber(PositionGetDouble(POSITION_SL))+","
             "\"tp\":"+JsonNumber(PositionGetDouble(POSITION_TP))+","
             "\"profit\":"+JsonNumber(PositionGetDouble(POSITION_PROFIT))+","
             "\"open_time_epoch\":"+IntegerToString(PositionGetInteger(POSITION_TIME))+
             "}";
     }
   return "{\"positions\":["+items+"]}";
  }

string ClosedTradesResult()
  {
   datetime now=TimeCurrent();
   datetime day_start=StringToTime(TimeToString(now,TIME_DATE));
   if(!HistorySelect(day_start,now))
      return "";
   string items="";
   int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0)
         continue;
      long entry=HistoryDealGetInteger(ticket,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY)
         continue;
      double profit=HistoryDealGetDouble(ticket,DEAL_PROFIT)
                    +HistoryDealGetDouble(ticket,DEAL_COMMISSION)
                    +HistoryDealGetDouble(ticket,DEAL_SWAP)
                    +HistoryDealGetDouble(ticket,DEAL_FEE);
      if(items!="") items+=",";
      items+="{"
             "\"ticket\":"+IntegerToString((long)ticket)+","
             "\"symbol\":\""+JsonEscape(HistoryDealGetString(ticket,DEAL_SYMBOL))+"\","
             "\"profit\":"+JsonNumber(profit)+","
             "\"close_time_epoch\":"+IntegerToString(HistoryDealGetInteger(ticket,DEAL_TIME))+
             "}";
     }
   return "{\"trades\":["+items+"]}";
  }

int StoredIndex(const string key)
  {
   for(int i=0;i<ArraySize(stored_keys);i++)
      if(stored_keys[i]==key)
         return i;
   return -1;
  }

string IdempotencyCacheFile()
  {
   return "ThangRod\\idempotency_"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+".csv";
  }

void PersistStoredResults()
  {
   if(!PersistIdempotency)
      return;
   FolderCreate("ThangRod",FILE_COMMON);
   int handle=FileOpen(IdempotencyCacheFile(),FILE_WRITE|FILE_CSV|FILE_COMMON,'\t');
   if(handle==INVALID_HANDLE)
     {
      Print("Could not persist idempotency cache: ",GetLastError());
      return;
     }
   for(int i=0;i<ArraySize(stored_keys);i++)
      FileWrite(handle,stored_keys[i],stored_results[i]);
   FileFlush(handle);
   FileClose(handle);
  }

void StoreResult(const string key,const string result,const bool persist=true)
  {
   if(key=="")
      return;
   int index=StoredIndex(key);
   if(index<0)
     {
      int max_items=MathMax(1,IdempotencyCacheMax);
      int size=ArraySize(stored_keys);
      if(size>=max_items)
        {
         for(int i=1;i<size;i++)
           {
            stored_keys[i-1]=stored_keys[i];
            stored_results[i-1]=stored_results[i];
           }
         ArrayResize(stored_keys,size-1);
         ArrayResize(stored_results,size-1);
        }
      index=ArraySize(stored_keys);
      ArrayResize(stored_keys,index+1);
      ArrayResize(stored_results,index+1);
      stored_keys[index]=key;
     }
   stored_results[index]=result;
   if(persist)
      PersistStoredResults();
  }

void LoadStoredResults()
  {
   if(!PersistIdempotency)
      return;
   int handle=FileOpen(IdempotencyCacheFile(),FILE_READ|FILE_CSV|FILE_COMMON,'\t');
   if(handle==INVALID_HANDLE)
      return;
   while(!FileIsEnding(handle))
     {
      string key=FileReadString(handle);
      string result=FileReadString(handle);
      if(key!="" && result!="")
         StoreResult(key,result,false);
     }
   FileClose(handle);
   PrintFormat("Loaded %d persisted idempotency results",ArraySize(stored_keys));
  }

string ExecuteResult(const string request)
  {
   string key=JsonString(request,"idempotency_key");
   int existing=StoredIndex(key);
   if(existing>=0)
      return stored_results[existing];
   if(!AllowExecution)
     {
      string blocked="{\"retcode\":10027,\"retcode_text\":\"EA execution is disabled\",\"ticket\":0}";
      StoreResult(key,blocked);
      return blocked;
     }
   if(AccountTypeName()=="REAL" && !AllowRealTrading)
     {
      string blocked="{\"retcode\":10027,\"retcode_text\":\"EA real trading is disabled\",\"ticket\":0}";
      StoreResult(key,blocked);
      return blocked;
     }
   string symbol=JsonString(request,"symbol");
   string side=JsonString(request,"side");
   double volume=JsonDouble(request,"volume");
   double sl=JsonDouble(request,"sl");
   double tp=JsonDouble(request,"tp");
   trade.SetExpertMagicNumber(ExpertMagicNumber);
   trade.SetTypeFillingBySymbol(symbol);
   string comment=StringSubstr(key,0,31);
   bool sent=(side=="BUY")
             ? trade.Buy(volume,symbol,0.0,sl,tp,comment)
             : trade.Sell(volume,symbol,0.0,sl,tp,comment);
   uint retcode=trade.ResultRetcode();
   ulong ticket=trade.ResultOrder();
   if(ticket==0) ticket=trade.ResultDeal();
   string result="{"
                 "\"retcode\":"+IntegerToString((long)retcode)+","
                 "\"retcode_text\":\""+JsonEscape(trade.ResultRetcodeDescription())+"\","
                 "\"ticket\":"+IntegerToString((long)ticket)+","
                 "\"price\":"+JsonNumber(trade.ResultPrice())+","
                 "\"sent\":"+(sent ? "true" : "false")+
                 "}";
   StoreResult(key,result);
   return result;
  }

void HandleRequest(const string request)
  {
   string id=JsonString(request,"id");
   string method=JsonString(request,"method");
   if(id=="" || method=="")
     {
      SendError(id,"invalid request");
      return;
     }
   if(method=="health") SendResult(id,HealthResult());
   else if(method=="account_info") SendResult(id,AccountResult());
   else if(method=="quote")
     {
      string result=QuoteResult(JsonString(request,"symbol"));
      if(result=="") SendError(id,"quote unavailable"); else SendResult(id,result);
     }
   else if(method=="symbol_info") SendResult(id,SymbolInfoResult(JsonString(request,"symbol")));
   else if(method=="positions") SendResult(id,PositionsResult());
   else if(method=="closed_trades_today")
     {
      string result=ClosedTradesResult();
      if(result=="") SendError(id,"history unavailable"); else SendResult(id,result);
     }
   else if(method=="execute_order") SendResult(id,ExecuteResult(request));
   else if(method=="order_status")
     {
      string key=JsonString(request,"idempotency_key");
      int index=StoredIndex(key);
      if(index<0) SendResult(id,"{\"found\":false}");
      else SendResult(id,"{\"found\":true,\"order\":"+stored_results[index]+"}");
     }
   else SendError(id,"unknown method");
  }

void ReadRequests()
  {
   if(socket_handle==INVALID_HANDLE || !SocketIsConnected(socket_handle))
      return;
   uint available=SocketIsReadable(socket_handle);
   if(available==0)
      return;
   char data[];
   int count=SocketRead(socket_handle,data,available,100);
   if(count<=0)
      return;
   receive_buffer+=CharArrayToString(data,0,count);
   int newline=StringFind(receive_buffer,"\n");
   while(newline>=0)
     {
      string request=StringSubstr(receive_buffer,0,newline);
      receive_buffer=StringSubstr(receive_buffer,newline+1);
      if(StringLen(request)>0)
         HandleRequest(request);
      newline=StringFind(receive_buffer,"\n");
     }
  }

int OnInit()
  {
   trade.SetExpertMagicNumber(ExpertMagicNumber);
   LoadStoredResults();
   EventSetTimer(1);
   EnsureConnected();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   PersistStoredResults();
   if(socket_handle!=INVALID_HANDLE)
      SocketClose(socket_handle);
   socket_handle=INVALID_HANDLE;
  }

void OnTimer()
  {
   if(EnsureConnected())
      ReadRequests();
  }
