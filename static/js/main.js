// small interactive JS: confirm toggles etc.
document.addEventListener("click", function(e){
  if(e.target.matches(".confirm-toggle")) {
    if(!confirm("Are you sure?")) e.preventDefault();
  }
});