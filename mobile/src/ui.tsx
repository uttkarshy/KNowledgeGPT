import React, {createContext, useContext, useEffect, useState} from 'react';
import {ActivityIndicator, KeyboardAvoidingView, Pressable, ScrollView, Text, TextInput, View, useColorScheme, type TextInputProps} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import * as Store from 'expo-secure-store';

const light={bg:'#F5F6EF',surface:'#FFFFFF',ink:'#172D29',muted:'#475F57',accent:'#185B4B',on:'#FFFFFF',line:'#CEDBD1',soft:'#DDEDE2',danger:'#9B3535'};
const dark={bg:'#10201D',surface:'#1B302B',ink:'#E7F0E8',muted:'#B2C9BA',accent:'#ACDDBA',on:'#163E31',line:'#3B534B',soft:'#263F37',danger:'#FFB7AF'};
type Mode='system'|'light'|'dark';
const Theme=createContext({c:light,mode:'system' as Mode,set:(_m:Mode)=>{}});
export function ThemeProvider({children}:{children:React.ReactNode}) {
  const [mode,setMode]=useState<Mode>('system');const os=useColorScheme();
  useEffect(()=>{Store.getItemAsync('appearance').then(v=>{if(v==='light'||v==='dark')setMode(v);}).catch(()=>{});},[]);
  return <Theme.Provider value={{mode,c:(mode==='system'?os:mode)==='dark'?dark:light,set:m=>{setMode(m);void Store.setItemAsync('appearance',m).catch(()=>{});}}}>{children}</Theme.Provider>;
}
export const useTheme=()=>useContext(Theme);
export function Label({children,small=false,heading=false}:{children:React.ReactNode;small?:boolean;heading?:boolean}) {
  const {c}=useTheme();
  return <Text accessibilityRole={heading?'header':undefined} selectable style={{fontSize:heading?23:small?14:17,lineHeight:heading?32:small?21:26,color:small?c.muted:c.ink,fontWeight:heading?'600':'400'}}>{children}</Text>;
}
export function Page({title,children}:{title:string;children:React.ReactNode}) {
  const {c}=useTheme();
  return <SafeAreaView edges={['left','right','bottom']} style={{flex:1,backgroundColor:c.bg}}><KeyboardAvoidingView style={{flex:1}} behavior="height">
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{width:'100%',maxWidth:720,alignSelf:'center',padding:20,paddingBottom:40,gap:14}}>
    <Text accessibilityRole="header" style={{fontFamily:'serif',fontSize:35,lineHeight:44,color:c.ink,marginBottom:4}}>{title}</Text>{children}</ScrollView></KeyboardAvoidingView></SafeAreaView>;
}
export function Card({children}:{children:React.ReactNode}) {const {c}=useTheme();return <View style={{padding:17,gap:10,borderColor:c.line,borderWidth:1,borderRadius:18,backgroundColor:c.surface}}>{children}</View>;}
export function Button({title,onPress,quiet=false,disabled=false,danger=false}:{title:string;onPress:()=>void;quiet?:boolean;disabled?:boolean;danger?:boolean}) {
  const {c}=useTheme();
  return <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress} style={({pressed})=>({paddingHorizontal:16,paddingVertical:12,minHeight:48,justifyContent:'center',borderRadius:14,opacity:disabled?.55:pressed?.8:1,backgroundColor:quiet?c.soft:danger?c.danger:c.accent})}>
    <Text style={{fontSize:16,fontWeight:'600',color:quiet?c.accent:danger?(c===dark?'#291111':'white'):c.on}}>{title}</Text></Pressable>;
}
export function Field({label,...props}:TextInputProps & {label:string}) {const {c}=useTheme();return <View style={{gap:5}}><Label small>{label}</Label><TextInput {...props} accessibilityLabel={label} placeholderTextColor={c.muted} style={{borderColor:c.line,borderWidth:1,borderRadius:12,minHeight:50,padding:12,color:c.ink,backgroundColor:c.surface,fontSize:17,textAlignVertical:props.multiline?'top':'center'}}/></View>;}
export function Notice({message}:{message:string}) {const {c}=useTheme();return message?<Text accessibilityLiveRegion="polite" selectable style={{color:c.ink,backgroundColor:c.soft,padding:12,borderRadius:10,lineHeight:22}}>{message}</Text>:null;}
export function Loading(){return <ActivityIndicator color={useTheme().c.accent} accessibilityLabel="Loading"/>;}
export function errorText(e:unknown){return e instanceof Error?e.message:'Could not complete the request. Please try again.';}
