import {useEffect,useState} from 'react';
import {Alert} from 'react-native';
import {router} from 'expo-router';
import {api,logout} from '../src/client';
import type {Profile} from '../src/types';
import {Page,Button,Label,Field,Card,Notice,useTheme,errorText} from '../src/ui';
import {useAction} from '../src/workspace';
export default function Settings(){
  const [me,setMe]=useState<Profile>(),[error,setError]=useState(''),[reason,setReason]=useState(''),[form,setForm]=useState<'help'|'delete'|''>('');const a=useAction(),theme=useTheme();
  async function profile(){try{setMe(await api<Profile>('/api/auth/me'));setError('');}catch(e){setError(errorText(e));}}
  useEffect(()=>{void profile();},[]);
  return <Page title="Account and settings"><Card>{me&&<><Label heading>{me.full_name||'Profile'}</Label><Label>{me.email}</Label><Label small>{me.is_verified?'Verified email':'Email verification pending'}{me.credit_balance!=null?' · '+me.credit_balance+' credits':''}</Label></>}<Notice message={error}/>{!me&&<Button quiet title="Refresh profile" onPress={()=>void profile()}/>}</Card>
    <Card><Label heading>Appearance</Label>{(['system','light','dark'] as const).map(m=><Button quiet={m!==theme.mode} key={m} title={(m==='system'?'Use device theme':m==='light'?'Light':'Dark')+(theme.mode===m?' · selected':'')} onPress={()=>theme.set(m)}/>)}</Card>
    <Button quiet title="Privacy policy" onPress={()=>router.push('/information?kind=privacy')}/><Button quiet title="Terms of service" onPress={()=>router.push('/information?kind=terms')}/>
    <Button quiet title="Contact UtkarshLabs" onPress={()=>setForm(form==='help'?'':'help')}/>{form==='help'&&<Card><Field label="Support message" multiline maxLength={1500} value={reason} onChangeText={setReason}/><Button title="Send to support" disabled={a.busy||reason.trim().length<3} onPress={()=>void a.run(async()=>{
      const r=await api<{reference:string}>('/api/support/contact',{reason:reason.trim()});setReason('');setForm('');a.setNotice('Request received · '+r.reference);
    })}/></Card>}
    <Button quiet title="Request account deletion" disabled={!me} onPress={()=>setForm(form==='delete'?'':'delete')}/>{form==='delete'&&me&&<Card><Label>Support will verify your email before removing your account, documents, extracted passages, conversations and sessions. Save anything you need first.</Label><Button danger title="Request deletion" disabled={a.busy} onPress={()=>Alert.alert('Request account deletion?',me.email,[{text:'Cancel',style:'cancel'},{text:'Request deletion',style:'destructive',onPress:()=>void a.run(async()=>{
      const r=await api<{reference:string}>('/api/support/deletion-request',{email:me.email,confirmation:'DELETE'},'POST',true);setForm('');a.setNotice('Deletion requested. Check your email for follow-up. Reference '+r.reference);
    })}])}/></Card>}
    <Notice message={a.notice}/><Button title="Sign out" onPress={()=>void a.run(logout)}/></Page>;
}
