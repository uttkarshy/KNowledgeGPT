export const mimeTypes: Record<string,string> = {
  pdf:'application/pdf', docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document', txt:'text/plain'
};
export function validateFile(name: string, size: number, max: number, extensions: string[]) {
  const extension = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
  if (!Object.hasOwn(mimeTypes, extension) || !extensions.includes(extension)) throw new Error('Choose a supported PDF, DOCX or TXT file.');
  if (!Number.isSafeInteger(size) || size <= 0 || size > max) throw new Error('Choose a non-empty file up to ' + Math.floor(max / 1048576) + ' MB.');
  return mimeTypes[extension];
}
export function httpsOrigin(value: string) {
  const u = new URL(value);
  if (u.protocol !== 'https:' || u.username || u.password || u.pathname !== '/' || u.search || u.hash) throw new Error('A secure service origin is required.');
  return u.origin;
}
