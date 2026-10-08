const btn=document.getElementById("voiceBtn");
const box=document.getElementById("voiceTranscript");
const status=document.getElementById("voiceStatus");
if(btn && box){
  const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SpeechRecognition){btn.disabled=true;btn.textContent="Voice unavailable";status.textContent="Use the text box instead; this browser does not support speech recognition."}
  else{
    const rec=new SpeechRecognition(); rec.lang="en-IN"; rec.interimResults=true;
    rec.onstart=()=>{btn.textContent="■ Stop voice";status.textContent="Listening…"};
    rec.onend=()=>{btn.textContent="🎙 Start voice";status.textContent="Voice capture ended."};
    rec.onerror=()=>{status.textContent="Voice recognition could not be used. You can type instead."};
    rec.onresult=e=>{let s="";for(let i=e.resultIndex;i<e.results.length;i++)s+=e.results[i][0].transcript;box.value=s};
    btn.onclick=()=>{try{rec.start()}catch(e){rec.stop()}};
  }
}
