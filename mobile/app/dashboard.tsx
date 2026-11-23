import {useState} from 'react';
import {router} from 'expo-router';
import {Button,Card,Field,Label,Loading,Notice,Page} from '../src/ui';
import {useAction,useWorkspace} from '../src/workspace';
import {api} from '../src/client';
import type {Base} from '../src/types';
export default function Dashboard(){
  const {data,error,refresh}=useWorkspace();const a=useAction();const [name,setName]=useState(''),[creating,setCreating]=useState(false);
  const open=(id:string)=>router.push({pathname:'/base',params:{id}});
  return <Page title="Your workspace"><Button quiet title="Account and settings" onPress={()=>router.push('/settings')}/>
    <Notice message={error||a.notice}/>{!data&&!error&&<Loading/>}<Button title="Create knowledge base" onPress={()=>setCreating(v=>!v)}/>
    {creating&&<Card><Field label="Knowledge base name" maxLength={255} value={name} onChangeText={setName}/><Button title="Create" disabled={a.busy||!name.trim()} onPress={()=>void a.run(async()=>{
      const kb=await api<Base>('/api/knowledge-bases',{name:name.trim()});setName('');setCreating(false);open(kb.id);
    })}/></Card>}
    {data&&<><Label heading>Knowledge bases</Label>{data.bases.filter(b=>!b.is_folder).map(b=><Card key={b.id}><Label heading>{b.name}</Label><Label small>{data.docs.filter(d=>d.knowledge_base_id===b.id).length} documents</Label><Button quiet title="Open documents and chat" onPress={()=>open(b.id)}/></Card>)}
    {!data.bases.length&&<Label>Create a knowledge base to add your first document.</Label>}
    <Label heading>Recent conversations</Label>{!data.chats.length&&<Label small>Start a chat from a knowledge base.</Label>}{data.chats.slice(0,10).map(s=><Button key={s.id} quiet title={s.title} onPress={()=>router.push({pathname:'/chat',params:{id:s.id}})}/>)}
    <Label heading>Recent documents</Label>{!data.docs.length&&<Label small>Your uploaded documents will appear here.</Label>}{data.docs.slice(0,8).map(d=><Button key={d.id} quiet title={d.name+' · '+d.status.replace(/_/g,' ')} onPress={()=>open(d.knowledge_base_id)}/>)}</>}
    <Button quiet title="Refresh workspace" onPress={refresh}/></Page>;
}
