import {Image} from 'react-native';
import {router} from 'expo-router';
import {Page,Card,Label,Button} from '../src/ui';
export default function Welcome(){return <Page title="KnowledgeGPT"><Card><Image accessibilityLabel="KnowledgeGPT" source={require('../assets/icon.png')} style={{width:64,height:64,borderRadius:16}}/><Label heading>Ask your documents</Label><Label>Build a knowledge base, ask a question, and open the sources behind each answer.</Label></Card>
<Button title="Sign in" onPress={()=>router.push('/auth?mode=login')}/><Button quiet title="Create an account" onPress={()=>router.push('/auth?mode=register')}/><Button quiet title="Privacy and data use" onPress={()=>router.push('/information?kind=privacy')}/></Page>;}
