let adminData=null;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url,opts={}){const r=await fetch(url,{headers:{'Content-Type':'application/json',...(opts.headers||{})},...opts});const d=await r.json();if(!r.ok)throw new Error(d.message||'Request failed');return d;}
function message(id,text,error=false){$(id).textContent=text;$(id).style.color=error?'#f07187':'#45d6a0';}
async function loadAdmin(){
  try{
    adminData=await api('/api/admin/overview');
    $('statMovies').textContent=adminData.movie_count;$('statShows').textContent=adminData.show_count;$('statBookings').textContent=adminData.booking_count;$('statRevenue').textContent='₹'+Number(adminData.revenue).toLocaleString('en-IN');
    $('movieRows').innerHTML=adminData.movies.map(m=>`<tr><td><div class="table-movie"><img src="${esc(m.poster)}" alt=""><b>${esc(m.title)}</b></div></td><td>${esc(m.genre)}</td><td>${esc(m.duration)}</td><td><button class="small-action" data-edit="${m.id}">Edit</button> <button class="small-action danger" data-delete="${m.id}">Delete</button></td></tr>`).join('');
    $('showMovie').innerHTML=adminData.movies.map(m=>`<option value="${m.id}">${esc(m.title)}</option>`).join('');
    $('showList').innerHTML=adminData.shows.map(s=>`<div class="schedule-row"><div><b>${esc(s.movie_title)}</b><small>${esc(s.theatre)} · ${esc(s.show_time)}</small></div><button class="small-action danger" data-show-delete="${s.id}">Remove</button></div>`).join('');
    $('bookingRows').innerHTML=adminData.bookings.length?adminData.bookings.map(b=>`<tr><td>${esc(b.id)}</td><td>${esc(b.customer)}</td><td>${esc(b.movie_title)}<small class="cell-sub">${esc(b.show_time)}</small></td><td>${esc(b.seats||'')}</td><td>₹${Number(b.total).toLocaleString('en-IN')}</td></tr>`).join(''):'<tr><td colspan="5">No bookings yet.</td></tr>';
    $('movieRows').querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>editMovie(+b.dataset.edit));
    $('movieRows').querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>removeMovie(+b.dataset.delete));
    $('showList').querySelectorAll('[data-show-delete]').forEach(b=>b.onclick=()=>removeShow(+b.dataset.showDelete));
  }catch(e){message('adminNotice',e.message,true);}
}
function resetMovieForm(){
  $('movieForm').reset();$('editMovieId').value='';$('movieFormTitle').textContent='Add a movie';$('saveMovie').textContent='Add movie + sample shows';$('cancelEdit').classList.add('hidden');
}
function editMovie(id){
  const m=adminData.movies.find(x=>x.id===id);if(!m)return;
  $('editMovieId').value=m.id;$('movieTitle').value=m.title||'';$('movieGenre').value=m.genre||'';$('movieDuration').value=m.duration||'';$('movieRating').value=m.rating||'';$('moviePoster').value=m.poster||'';$('movieDescription').value=m.description||'';
  $('movieFormTitle').textContent='Edit movie';$('saveMovie').textContent='Save movie changes';$('cancelEdit').classList.remove('hidden');$('movieForm').scrollIntoView({behavior:'smooth',block:'center'});
}
async function removeMovie(id){
  const m=adminData.movies.find(x=>x.id===id);if(!m||!confirm(`Delete "${m.title}"?`))return;
  try{const d=await api('/api/admin/movies/'+id,{method:'DELETE'});message('adminNotice',d.message);await loadAdmin();}catch(e){message('adminNotice',e.message,true);}
}
async function removeShow(id){
  if(!confirm('Remove this showtime?'))return;
  try{const d=await api('/api/admin/shows/'+id,{method:'DELETE'});message('adminNotice',d.message);await loadAdmin();}catch(e){message('adminNotice',e.message,true);}
}
$('movieForm').onsubmit=async e=>{
  e.preventDefault();const id=$('editMovieId').value;
  const payload={title:$('movieTitle').value,genre:$('movieGenre').value,duration:$('movieDuration').value,rating:$('movieRating').value,poster:$('moviePoster').value,description:$('movieDescription').value};
  try{const d=await api(id?'/api/admin/movies/'+id:'/api/admin/movies',{method:id?'PUT':'POST',body:JSON.stringify(payload)});message('movieMessage',d.message);resetMovieForm();await loadAdmin();}
  catch(err){message('movieMessage',err.message,true);}
};
$('cancelEdit').onclick=resetMovieForm;
$('showForm').onsubmit=async e=>{
  e.preventDefault();
  try{const d=await api('/api/admin/shows',{method:'POST',body:JSON.stringify({movie_id:$('showMovie').value,theatre:$('showTheatre').value,show_time:$('showTime').value})});message('showMessage',d.message);$('showTime').value='';await loadAdmin();}
  catch(err){message('showMessage',err.message,true);}
};
$('refreshAdmin').onclick=loadAdmin;
loadAdmin();
