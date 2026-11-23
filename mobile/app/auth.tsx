import {useLocalSearchParams,router} from 'expo-router';
import {useState} from 'react';
import {Page,Label,Field,Button,Notice,errorText} from '../src/ui';
import {api,login} from '../src/client';
const titles: Record<string,string>={login:'Sign in',register:'Create account',forgot:'Forgot password',reset:'Reset password',verify:'Verify email'};
export default function Auth(){
  const {mode='login'}=useLocalSearchParams<{mode:string}>();return <Form key={mode} mode={titles[mode]?mode:'login'}/>;
}
function Form({mode}:{mode:string}){
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[token,setToken]=useState(''),[name,setName]=useState(''),[busy,setBusy]=useState(false),[msg,setMsg]=useState('');
  const mail=['login','register','forgot'].includes(mode),pass=['login','register','reset'].includes(mode);
  async function submit(){
    if (busy)return;setBusy(true);setMsg('');
    try{
      if(mode==='login'){await login(email.trim(),password);return;}
      let raw=token.trim();
      if(raw.startsWith('https://'))raw=new URL(raw).searchParams.get('token')||'';
      const data=mode==='register'?{email:email.trim(),password,full_name:name.trim()||null}:mode==='forgot'?{email:email.trim()}:mode==='reset'?{token:raw,new_password:password}:{token:raw};
      const path=mode==='register'?'register':mode==='forgot'?'forgot-password':mode==='reset'?'reset-password':'verify-email';
      await api('/api/auth/'+path,data,'POST',true);setToken('');setPassword('');
      setMsg(mode==='register'?'Account created. Check your email for verification, then sign in.':mode==='forgot'?'If an account exists, a reset link will arrive by email.':mode==='reset'?'Password updated. Sign in with your new password.':'Email verified. You can sign in.');
    }catch(e){setMsg(errorText(e));}finally{setBusy(false);}
  }
  return <Page title={titles[mode]}>{mode==='register'&&<Field label="Name (optional)" value={name} onChangeText={setName} maxLength={255}/>}
    {mail&&<Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email"/>}
    {!mail&&<Field label="Email link or token" value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false} secureTextEntry/>}
    {pass&&<Field label={mode==='reset'?'New password':'Password'} value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" autoComplete={mode==='login'?'current-password':'new-password'}/>}
    {['register','reset'].includes(mode)&&<Label small>Use at least 10 characters with uppercase, lowercase, a number and a symbol.</Label>}
    {mode==='register'&&<Label small>Your selected files and relevant passages are processed by the service and its AI providers. Read Privacy and Terms before creating an account.</Label>}
    <Notice message={msg}/><Button title={busy?'Working…':titles[mode]} disabled={busy||(mail&&!email.trim())||(pass&&!password)||(!mail&&!token.trim())} onPress={()=>void submit()}/>
    {(mode==='login'?['forgot','verify','register']:mode==='forgot'?['reset','login']:['login']).map(m=><Button key={m} quiet title={titles[m]} onPress={()=>router.replace({pathname:'/auth',params:{mode:m}})}/>)}
    {mode==='register'&&['privacy','terms'].map(k=><Button key={k} quiet title={k==='privacy'?'Privacy policy':'Terms of service'} onPress={()=>router.push({pathname:'/information',params:{kind:k}})}/>)}</Page>;
}
