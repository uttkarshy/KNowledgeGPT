import {useEffect,useRef,useState} from 'react';
import {Alert} from 'react-native';
import {useLocalSearchParams,router} from 'expo-router';
import {Page,Card,Label,Button,Notice,Loading} from '../src/ui';
import {api} from '../src/client';
import {useWorkspace,useAction,limits,enc} from '../src/workspace';
import {upload} from '../src/upload';
import type {Doc,Conversation} from '../src/types';
export default function Library(){
  const {id}=useLocalSearchParams<{id:string}>();const {data,error,refresh}=useWorkspace(id);const a=useAction();
  const [expanded,setExpanded]=useState(''),[progress,setProgress]=useState('');
  const ctl=useRef<AbortController|null>(null);useEffect(()=>()=>ctl.current?.abort(),[]);
  const open=(cid:string)=>router.push({pathname:'/chat',params:{id:cid}});
  const docPath=(d:Doc)=>'/api/documents/'+enc(d.id);
  function processDoc(d:Doc){void a.run(async()=>{
    const cap=await limits();let credits=d.estimated_credits;
    if(cap && credits==null)credits=(await api<Doc>(docPath(d)+'/estimate',{})).estimated_credits;
    if(cap && typeof credits!=='number')throw new Error('The service did not return a processing estimate.');
    Alert.alert('Process '+d.name+'?',cap?'Estimated cost: '+credits+' KnowledgeGPT credits.':'Index this file for questions and citations.',[
      {text:'Cancel',style:'cancel'},{text:'Start processing',onPress:()=>void a.run(async()=>{await api('/api/documents/confirm',{document_id:d.id});refresh();})}]);
  });}
  return <Page title={data?.bases.find(b=>b.id===id)?.name||'Knowledge base'}><Notice message={error||a.notice}/>{!data&&!error&&<Loading/>}
    <Button title="New chat" disabled={a.busy||!data} onPress={()=>void a.run(async()=>open((await api<Conversation>('/api/chat/sessions',{knowledge_base_id:id})).id))}/>
    <Card><Label heading>Documents</Label><Label small>Selected files go to KnowledgeGPT storage. Processing sends extracted text to the service’s AI provider. Review the estimate before indexing.</Label>
    <Button title="Choose PDF, DOCX or TXT" disabled={a.busy||!data} onPress={()=>void a.run(async()=>{const current=new AbortController();ctl.current=current;setProgress('');
      try{await upload(id,current.signal,setProgress);}catch(e){setProgress('');throw e;}finally{ctl.current=null;refresh();}
    })}/><Notice message={progress}/>{a.busy&&ctl.current&&<Button quiet title="Cancel upload" onPress={()=>ctl.current?.abort()}/>}</Card>
    {data?.docs.map(d=><Card key={d.id}><Label heading>{d.name}</Label><Label small>{d.status.replace(/_/g,' ')} · {d.processing_progress_pct}%</Label>
      <Button quiet title={expanded===d.id?'Hide details':'Document details'} onPress={()=>setExpanded(expanded===d.id?'':d.id)}/>
      {expanded===d.id&&<><Label small>{Math.ceil(d.original_size_bytes/1024)} KB · {d.chunk_count} indexed passages{d.page_count?' · '+d.page_count+' pages':''}</Label>{d.status_detail&&<Label small>{d.status_detail}</Label>}
        <Button quiet title="Delete document" disabled={a.busy} onPress={()=>Alert.alert('Delete this document?',d.name,[{text:'Cancel',style:'cancel'},{text:'Delete',style:'destructive',onPress:()=>void a.run(async()=>{await api(docPath(d),undefined,'DELETE');refresh();})}])}/></>}
      {d.status==='pending'&&<Button title="Review and process" disabled={a.busy} onPress={()=>processDoc(d)}/>}
      {d.status==='failed'&&d.retryable&&<Button title="Retry processing" disabled={a.busy} onPress={()=>void a.run(async()=>{await api(docPath(d)+'/retry',{});refresh();})}/>}</Card>)}
    <Label heading>Conversations</Label>{data?.chats.map(s=><Button quiet key={s.id} title={s.title} onPress={()=>open(s.id)}/>)}<Button quiet title="Refresh status" onPress={refresh}/></Page>;
}
