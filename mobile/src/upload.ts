import * as Picker from 'expo-document-picker';
import * as Files from 'expo-file-system/legacy';
import {api} from './client';
import {limits} from './workspace';
import {mimeTypes,validateFile} from './validation';

export async function upload(base:string,signal:AbortSignal,progress:(text:string)=>void){
  const allowed=await limits(signal);
  const picked=await Picker.getDocumentAsync({type:Object.values(mimeTypes),copyToCacheDirectory:true,multiple:false});
  if(picked.canceled)return;
  const f=picked.assets[0];
  try{
    if(signal.aborted)return;
    const info=await Files.getInfoAsync(f.uri);
    const size=f.size??(info.exists?info.size:0);
    const mime=validateFile(f.name,size,allowed?.max_size_bytes??200*1048576,allowed?.allowed_extensions??Object.keys(mimeTypes));
    progress('Preparing upload…');
    const result=await api<{document_id:string;upload_url:string}>('/api/documents/upload-url',{knowledge_base_id:base,filename:f.name,size_bytes:size,content_type:mime},'POST',false,signal);
    const u=new URL(result.upload_url);
    if(u.protocol!=='https:'||u.username||u.password)throw new Error('The upload service returned an insecure storage address.');
    const task=Files.createUploadTask(result.upload_url,f.uri,{httpMethod:'PUT',uploadType:Files.FileSystemUploadType.BINARY_CONTENT,headers:{'Content-Type':mime}},p=>{
      if(p.totalBytesExpectedToSend>0)progress('Uploading · '+Math.round(100*p.totalBytesSent/p.totalBytesExpectedToSend)+'%');
    });
    const cancel=()=>{void task.cancelAsync().catch(()=>{});};
    if(signal.aborted)return;
    const timeout=setTimeout(cancel,180000);signal.addEventListener('abort',cancel);
    try{
      const res=await task.uploadAsync();
      if(!res||res.status<200||res.status>=300)throw new Error('Upload interrupted. Remove the pending entry and select the file again.');
    }finally{clearTimeout(timeout);signal.removeEventListener('abort',cancel);}
    if(allowed){progress('Estimating processing cost…');await api('/api/documents/'+encodeURIComponent(result.document_id)+'/estimate',{},'POST',false,signal);}
    progress('File uploaded. Review the pending document to start processing.');
  }finally{
    if(Files.cacheDirectory&&f.uri.startsWith(Files.cacheDirectory))await Files.deleteAsync(f.uri,{idempotent:true}).catch(()=>{});
  }
}
