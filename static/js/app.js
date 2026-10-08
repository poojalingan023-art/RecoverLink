document.addEventListener("DOMContentLoaded",()=>{
  document.querySelectorAll(".alert").forEach(a=>setTimeout(()=>{try{bootstrap.Alert.getOrCreateInstance(a).close()}catch(e){}},5000));
});
