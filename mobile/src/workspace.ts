import {useCallback,useRef,useState} from 'react';
import {useFocusEffect} from 'expo-router';
import {api,ApiError} from './client';
import type {Base,Doc,Conversation,Limits} from './types';
import {errorText} from './ui';

export const enc=encodeURIComponent;
export async function limits(signal?:AbortSignal):Promise<Limits|null>{
  try{return await api<Limits>('/api/documents/limits',undefined,'GET',false,signal);}
  catch(e){if(e instanceof ApiError&&e.status===404)return null;throw e;}
}
export function useWorkspace(baseId?:string){
  const [data,setData]=useState<{bases:Base[];docs:Doc[];chats:Conversation[]}|null>(null);
  const [error,setError]=useState('');const [revision,setRevision]=useState(0);
  const refresh=useCallback(()=>setRevision(v=>v+1),[]);
  useFocusEffect(useCallback(()=>{
    const ctl=new AbortController();let timer:ReturnType<typeof setTimeout>;
    const suffix=baseId?'?knowledge_base_id='+enc(baseId):'';
    async function reload(){
      try{
        const get=<T,>(p:string)=>api<T>(p,undefined,'GET',false,ctl.signal);
        const [bases,docs,chats]=await Promise.all([get<Base[]>('/api/knowledge-bases'),get<Doc[]>('/api/documents'+suffix),get<Conversation[]>('/api/chat/sessions'+suffix)]);
        if(ctl.signal.aborted)return;
        setData({bases,docs,chats});setError('');
        if(docs.some(d=>!['pending','completed','failed'].includes(d.status)))timer=setTimeout(reload,3500);
      }catch(e){if(!ctl.signal.aborted)setError(errorText(e));}
    }
    void reload();return()=>{ctl.abort();clearTimeout(timer);};
  },[baseId,revision]));
  return {data,error,refresh};
}
export function useAction(){
  const lock=useRef(false);const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function run(fn:()=>Promise<void>){
    if(lock.current)return;lock.current=true;setBusy(true);setNotice('');
    try{await fn();}catch(e){setNotice(errorText(e));}finally{lock.current=false;setBusy(false);}
  }
  return {busy,notice,setNotice,run};
}
