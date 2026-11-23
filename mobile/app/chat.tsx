import {useCallback,useEffect,useRef,useState} from 'react';
import {ScrollView,Text,View,KeyboardAvoidingView} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {useFocusEffect, useLocalSearchParams} from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import {randomUUID} from 'expo-crypto';
import Markdown from 'react-native-markdown-display';
import {api,ask,ApiError} from '../src/client';
import {Button,Card,Field,Label,Loading,Notice,errorText,useTheme} from '../src/ui';
import {enc,useAction} from '../src/workspace';
import type {Message,Citation} from '../src/types';
const rules={image:()=>null,html_inline:()=>null,html_block:()=>null};
function Answer({item}:{item:Message}){
  const {c}=useTheme();const [sources,show]=useState(false),[report,setReport]=useState(false),[reason,setReason]=useState('');const a=useAction();
  return <Card><Label small>{item.role==='assistant'?'KnowledgeGPT':'You'}</Label>
    <Markdown onLinkPress={()=>false} rules={rules} style={{body:{color:c.ink,fontSize:17,lineHeight:25},code_inline:{backgroundColor:c.soft,color:c.ink},fence:{backgroundColor:c.soft,color:c.ink},code_block:{backgroundColor:c.soft,color:c.ink}}}>{item.content}</Markdown>
    {item.citations?.length>0&&<Button quiet title={(sources?'Hide':'View')+' sources ('+item.citations.length+')'} onPress={()=>show(!sources)}/>}
    {sources&&item.citations.map((s:Citation,i)=><View key={i} style={{borderLeftWidth:3,borderColor:c.accent,paddingLeft:10,gap:4}}><Label>[{i+1}] {s.document_name}{s.page_number?' · p. '+s.page_number:''}</Label>{s.section&&<Label small>{s.section}</Label>}<Label small>{s.excerpt}</Label></View>)}
    {item.role==='assistant'&&<><Button quiet title="Copy answer" onPress={()=>void a.run(async()=>{await Clipboard.setStringAsync(item.content);a.setNotice('Answer copied.');})}/>
    <Button quiet title="Report answer" onPress={()=>setReport(!report)}/>{report&&<><Field label="Reason for reporting" value={reason} maxLength={1500} onChangeText={setReason}/><Button title="Send report" disabled={a.busy||reason.trim().length<3} onPress={()=>void a.run(async()=>{
      const r=await api<{reference:string}>('/api/support/report-answer',{message_id:item.id,reason:reason.trim()});setReport(false);setReason('');a.setNotice('Report received · '+r.reference);
    })}/></>}<Notice message={a.notice}/></>}</Card>;
}
export default function Chat(){
  const {id}=useLocalSearchParams<{id:string}>();const path='/api/chat/sessions/'+enc(id)+'/messages';const {c}=useTheme();
  const [history,setHistory]=useState<Message[]>([]),[draft,setDraft]=useState(''),[partial,setPartial]=useState(''),[pending,setPending]=useState('');
  const [busy,setBusy]=useState(false),[loaded,setLoaded]=useState(false),[note,setNote]=useState(''),[cost,setCost]=useState<number|null>(null);
  const controller=useRef<AbortController|null>(null),alive=useRef(true),retry=useRef<{q:string;key:string;before:string}|null>(null);
  const scroll=useRef<ScrollView>(null),atEnd=useRef(true);
  const load=useCallback(async(signal?:AbortSignal)=>{const rows=await api<Message[]>(path,undefined,'GET',false,signal);if(!signal?.aborted&&alive.current){setHistory(rows);setLoaded(true);}return rows;},[path]);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;controller.current?.abort();};},[]);
  useFocusEffect(useCallback(()=>{const ctl=new AbortController();
    void load(ctl.signal).catch(e=>{if(!ctl.signal.aborted)setNote(errorText(e));});
    void api<{chat_credits:number}>('/api/billing/credits',undefined,'GET',false,ctl.signal).then(v=>{if(!ctl.signal.aborted)setCost(v.chat_credits);}).catch(()=>{});
    return()=>ctl.abort();},[load]));
  async function send(){
    const q=draft.trim();if(!loaded||!q||controller.current)return;
    const ctl=new AbortController();controller.current=ctl;setBusy(true);setNote('');
    try{
      const prev=retry.current;
      if(prev&&prev.q===q){
        const recent=await load(ctl.signal);const last=recent[recent.length-1];
        if(last&&last.id!==prev.before&&last.role==='assistant'&&recent[recent.length-2]?.content===q){
          setNote('The previous answer was already saved.');retry.current=null;setDraft('');return;
        }
      }
      const key=prev?.q===q?prev.key:randomUUID();retry.current={q,key,before:history.at(-1)?.id||''};
      setPending(q);setPartial('');setDraft('');atEnd.current=true;
      let answer='',saved:Message|undefined;
      await ask(id,q,key,ctl.signal,e=>{
        if(ctl.signal.aborted||!alive.current)return;
        if(e.type==='error')throw new Error('The service could not complete the answer. Check history and retry.');
        if(e.delta){answer+=e.delta;setPartial(answer);}
        if((e.type==='done'||e.type==='no_answer')&&e.message_id)saved={id:e.message_id,role:'assistant',content:answer,citations:e.citations||[]};
      });
      if(!alive.current)return;
      if(saved){const item=saved;setHistory(v=>[...v,{id:key,role:'user',content:q,citations:[]},item]);}
      retry.current=null;
      await load(ctl.signal);
    }catch(e){
      if(alive.current){
        setNote(e instanceof ApiError&&e.status===402?'Your KnowledgeGPT account has insufficient credits.':errorText(e));
        if(retry.current)setDraft(q);
      }
    }finally{controller.current=null;if(alive.current){setBusy(false);setPending('');setPartial('');}}
  }
  return <SafeAreaView edges={['left','right','bottom']} style={{flex:1,backgroundColor:c.bg}}><KeyboardAvoidingView behavior="height" style={{flex:1}}>
    <ScrollView ref={scroll} keyboardShouldPersistTaps="handled" onScroll={e=>{const v=e.nativeEvent;atEnd.current=v.contentSize.height-v.layoutMeasurement.height-v.contentOffset.y<100;}} scrollEventThrottle={80} onContentSizeChange={()=>{if(atEnd.current)scroll.current?.scrollToEnd({animated:false});}} contentContainerStyle={{padding:16,gap:12}}>
    {!loaded&&!note&&<Loading/>}{loaded&&!history.length&&!pending&&<Card><Label heading>Ask a question</Label><Label>Use your knowledge base to find an answer and its supporting passages.</Label></Card>}
    {history.filter(m=>m.role!=='system').map(m=><Answer key={m.id} item={m}/>)}{pending&&<Card><Label>{pending}</Label><Text selectable style={{color:c.ink,fontSize:17}}>{partial||'Searching your documents…'}</Text></Card>}
    </ScrollView><View style={{padding:12,gap:6,backgroundColor:c.surface}}><Notice message={note}/>
    {note&&!busy&&<Button quiet title="Reload conversation" onPress={()=>{void load().then(()=>setNote('')).catch(e=>setNote(errorText(e)));}}/>}
    <Field label="Question" multiline value={draft} editable={!busy} maxLength={4000} onChangeText={setDraft}/>
    {busy?<Button quiet title="Stop response" onPress={()=>controller.current?.abort()}/>:<Button title={(retry.current?.q===draft.trim()?'Retry question':'Send question')+(cost!=null?' · '+cost+' credits':'')} disabled={!draft.trim()||!loaded} onPress={()=>void send()}/>}</View></KeyboardAvoidingView></SafeAreaView>;
}
