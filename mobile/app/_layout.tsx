import {Stack} from 'expo-router';
import {useEffect,useSyncExternalStore} from 'react';
import {StatusBar} from 'expo-status-bar';
import {ThemeProvider,useTheme,Page,Button,Notice,Loading} from '../src/ui';
import {session,restore} from '../src/client';
function Screens(){
  const {c}=useTheme();const state=useSyncExternalStore(session.subscribe,session.get);
  useEffect(()=>{void restore();},[]);
  if(state==='storage-error')return <Page title="Device storage"><Notice message="Android could not open protected storage. Unlock your device and retry."/><Button title="Retry" onPress={()=>void restore()}/></Page>;
  if(state==='loading')return <Page title="KnowledgeGPT"><Loading/></Page>;
  return <><StatusBar style={c.bg==='#10201D'?'light':'dark'}/><Stack screenOptions={{headerStyle:{backgroundColor:c.bg},headerTintColor:c.ink,headerShadowVisible:false,headerTitleStyle:{fontSize:17},contentStyle:{backgroundColor:c.bg}}}>
    <Stack.Protected guard={state==='anonymous'}><Stack.Screen name="index" options={{title:'UtkarshLabs'}}/><Stack.Screen name="auth" options={{title:'Account access'}}/></Stack.Protected>
    <Stack.Protected guard={state==='signed-in'}><Stack.Screen name="dashboard" options={{title:'KnowledgeGPT'}}/><Stack.Screen name="base" options={{title:'Knowledge base'}}/><Stack.Screen name="chat" options={{title:'Conversation'}}/><Stack.Screen name="settings" options={{title:'KnowledgeGPT'}}/></Stack.Protected>
    <Stack.Screen name="information" options={{title:'UtkarshLabs'}}/>
  </Stack></>;
}
export default function Layout(){return <ThemeProvider><Screens/></ThemeProvider>;}
