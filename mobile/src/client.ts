import {fetch as nativeFetch} from 'expo/fetch';
import * as SecureStore from 'expo-secure-store';
import {AnswerStream, type StreamEvent} from './stream';
import {httpsOrigin} from './validation';

export const origin = httpsOrigin(process.env.EXPO_PUBLIC_API_ORIGIN || 'https://knowledgegpt.utkarshlabs.com');
const refreshKey = 'knowledgegpt.refresh.v1.' + new URL(origin).host.replace(/[^A-Za-z0-9.-]/g,'_');
type State = 'loading' | 'anonymous' | 'signed-in' | 'storage-error';
type Pair = {access_token: string; refresh_token: string};
let state: State = 'loading';
let access = '', refresh = '', epoch = 0;
let rotation: Promise<string> | undefined;
let storageQueue: Promise<unknown> = Promise.resolve();
const listeners = new Set<() => void>();
export const session = {get: () => state, subscribe: (f: () => void) => {listeners.add(f); return () => {listeners.delete(f);};}};
function publish(next: State) {state = next; listeners.forEach(f => f());}
function persist(value: string) {
  const action = () => value ? SecureStore.setItemAsync(refreshKey, value) : SecureStore.deleteItemAsync(refreshKey);
  const op = storageQueue.then(action, action); storageQueue = op.catch(() => {}); return op;
}
export async function restore() {
  const generation = epoch;
  try {
    const token = await SecureStore.getItemAsync(refreshKey);
    if (generation === epoch) {refresh = token || ''; publish(refresh ? 'signed-in' : 'anonymous');}
  } catch {publish('storage-error');}
}
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {super(message); this.status = status;}
}
async function checked(path: string, body: unknown, method: string, token: string, signal: AbortSignal, extras: Record<string,string> = {}) {
  if (!path.startsWith('/api/') || path.includes('://')) throw new Error('Invalid service path.');
  const r = await nativeFetch(origin + path, {method, signal, redirect:'error',
    headers:{Accept:'application/json', ...(body !== undefined ? {'Content-Type':'application/json'}:{}), ...(token ? {Authorization:'Bearer '+token}:{}), ...extras},
    body: body === undefined ? undefined : JSON.stringify(body)});
  if (!r.ok) {
    let detail: unknown;
    try {detail = (await r.json()).detail;} catch {}
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(v => v.message || v.msg).filter(Boolean).join(' ') : '';
    throw new ApiError(r.status, r.status >= 500 ? 'The service is unavailable. Try again shortly.' : r.status === 404 && path.startsWith('/api/support/') ? 'This support feature is awaiting service deployment.' : (msg || 'Request failed ('+r.status+').'));
  }
  return r;
}
async function timed<T>(ms: number, fn: (signal: AbortSignal) => Promise<T>, external?: AbortSignal) {
  const ctl = new AbortController(); const abort = () => ctl.abort();
  const timer = setTimeout(abort, ms); external?.addEventListener('abort', abort); if (external?.aborted) abort();
  try {return await fn(ctl.signal);}
  catch (e) {
    if (ctl.signal.aborted) throw new Error(external?.aborted ? 'Stopped.' : 'Request timed out. Check your connection and retry.');
    if (e instanceof TypeError) throw new Error('Cannot reach KnowledgeGPT. Check your internet connection and retry.');
    throw e;
  } finally {clearTimeout(timer); external?.removeEventListener('abort', abort);}
}
async function savePair(pair: Pair, version: number) {
  if (version !== epoch || !pair.access_token || !pair.refresh_token) throw new Error('Your session changed. Sign in again.');
  await persist(pair.refresh_token);
  if (version !== epoch) throw new Error('Session changed.');
  access = pair.access_token; refresh = pair.refresh_token; publish('signed-in'); return access;
}
export async function login(email: string, password: string) {
  const version = ++epoch;
  await timed(25000, async signal => savePair(await (await checked('/api/auth/login',{email,password},'POST','',signal)).json(), version));
}
async function clear() {
  ++epoch; rotation = undefined; access = ''; refresh = ''; publish('anonymous');
  try {await persist('');} catch {publish('storage-error'); throw new Error('Could not clear protected storage. Clear app data in Android settings.');}
}
export async function logout() {
  const token = refresh; await clear();
  if (token) await timed(8000, async signal => {await checked('/api/auth/logout',{refresh_token:token},'POST','',signal);}).catch(()=>{});
}
async function renew() {
  if (!refresh) throw new ApiError(401,'Sign in to continue.');
  if (rotation) return rotation;
  const version = epoch; const token = refresh;
  const op = timed(25000, async signal => {
    try {return await savePair(await (await checked('/api/auth/refresh',{refresh_token:token},'POST','',signal)).json(), version);}
    catch(e) {if (version === epoch && e instanceof ApiError && [401,403].includes(e.status)) await clear(); throw e;}
  });
  rotation = op; try {return await op;} finally {if (rotation === op) rotation = undefined;}
}
async function authorized(path:string,body:unknown,method:string,signal:AbortSignal,headers?:Record<string,string>) {
  const version=epoch, token=access || await renew();
  try {return await checked(path,body,method,token,signal,headers);}
  catch(e) {
    if (!(e instanceof ApiError) || e.status !== 401 || version !== epoch) throw e;
    const next = access && access !== token ? access : await renew();
    if (version !== epoch) throw new Error('Session changed.');
    return checked(path,body,method,next,signal,headers);
  }
}
export function api<T>(path:string,body?:unknown,method=body === undefined ? 'GET':'POST', pub=false, signal?:AbortSignal):Promise<T> {
  return timed(45000,async s=>{
    const r = pub ? await checked(path,body,method,'',s) : await authorized(path,body,method,s);
    return r.status === 204 ? undefined : await r.json();
  }, signal);
}
export async function ask(id:string,question:string,key:string,signal:AbortSignal,onEvent:(e:StreamEvent)=>void) {
  await timed(180000,async s=>{
    const r=await authorized('/api/chat/sessions/'+encodeURIComponent(id)+'/ask',{question},'POST',s,{'Accept':'text/event-stream','Idempotency-Key':key});
    if (!r.body || !r.headers.get('content-type')?.includes('text/event-stream')) throw new Error('The service did not return an answer stream.');
    const reader=r.body.getReader(); const decoder=new TextDecoder(); const parser=new AnswerStream();
    try {
      for (;;) {
        const {done,value}=await reader.read();
        parser.push(done ? decoder.decode() : decoder.decode(value,{stream:true})).forEach(onEvent);
        if (done) break;
      }
      parser.finish();
    } finally {await reader.cancel().catch(()=>{}); reader.releaseLock();}
  },signal);
}
