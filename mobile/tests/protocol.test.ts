import {test} from 'node:test';
import assert from 'node:assert/strict';
import {AnswerStream} from '../src/stream.ts';
import {validateFile,httpsOrigin} from '../src/validation.ts';

test('stream survives split UTF-8, CRLF, comments and an empty network read',()=>{
  const bytes=new TextEncoder().encode(': ping\r\n\r\ndata: {"type":"delta","delta":"हिंदी"}\r\n\r\ndata: {"type":"done","message_id":"id","citations":[]}\n\n');
  const parser=new AnswerStream(),decoder=new TextDecoder();
  const events=Array.from(bytes).flatMap(b=>parser.push(decoder.decode(Uint8Array.of(b),{stream:true})));
  parser.push(decoder.decode());parser.finish();assert.deepEqual(events.map(e=>e.type),['delta','done']);assert.equal(events[0].delta,'हिंदी');
});
test('no-answer and explicit provider errors are terminal',()=>{
  for(const type of ['no_answer','error']){const s=new AnswerStream();s.push('data: '+JSON.stringify({type})+'\n\n');s.finish();}
});
test('dropped connections and corrupt frames cannot be displayed as saved',()=>{
  const s=new AnswerStream();s.push('data: {"type":"delta","delta":"draft"}\n\n');assert.throws(()=>s.finish());assert.throws(()=>s.push('data: junk\n\n'));
});
test('rejects an event after the terminal frame',()=>{
  const s=new AnswerStream();s.push('data: {"type":"done"}\n\n');assert.throws(()=>s.push('data: {"type":"error"}\n\n'));
});
test('picked files must match both app and server rules',()=>{
  assert.equal(validateFile('Notes.PDF',8,8,['pdf']),'application/pdf');
  for(const [name,size] of [['notes.doc',8],['notes.pdf',0],['notes.pdf',9],['notes.pdf.exe',1],['constructor',4]] as const)
    assert.throws(()=>validateFile(name,size,8,['pdf']));
});
test('API origin cannot redirect credentials via a configured URL path',()=>{
  assert.equal(httpsOrigin('https://knowledgegpt.utkarshlabs.com/'),'https://knowledgegpt.utkarshlabs.com');
  for(const url of ['http://localhost','https://example.test/foo','https://u:p@example.test','https://example.test/?x=y'])assert.throws(()=>httpsOrigin(url));
});
