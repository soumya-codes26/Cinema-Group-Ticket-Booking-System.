let movies = [], shows = [], selected = new Set(), currentShow = null, activeMovie = null;
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(url, opts={}) {
  const r = await fetch(url, opts); const d = await r.json();
  if (!r.ok) throw new Error(d.message || 'Request failed'); return d;
}
function notice(msg, error=false) { $('notice').textContent=msg; $('notice').style.color=error?'#f07187':'#45d6a0'; }
function filteredMovies() {
  const q=$('movieSearch').value.trim().toLowerCase(), genre=$('genreFilter').value;
  return movies.filter(m => (!q || (m.title+' '+m.genre+' '+m.description).toLowerCase().includes(q)) && (!genre || (m.genre||'').toLowerCase().includes(genre)));
}
function renderMovies() {
  const list=filteredMovies();
  $('movieGrid').innerHTML=list.map(m=>`<article class="movie ${m.id===activeMovie?'active':''}" data-id="${m.id}">
    <div class="poster" style="background-image:url('${esc(m.poster || '')}')"><span class="rating">★ ${esc(m.rating || 'NR')}</span></div>
    <div class="movie-info"><h3>${esc(m.title)}</h3><p>${esc(m.genre||'General')} · ${esc(m.duration||'Duration TBA')}</p><p class="movie-description">${esc(m.description||'')}</p></div></article>`).join('');
  $('emptyMovies').classList.toggle('hidden',list.length>0);
  $('movieGrid').querySelectorAll('.movie').forEach(el=>el.onclick=()=>chooseMovie(+el.dataset.id));
}
function fillGenreFilter() {
  const current=$('genreFilter').value;
  const genres=[...new Set(movies.flatMap(m=>(m.genre||'').split(/[•,]/).map(x=>x.trim()).filter(Boolean)))].sort();
  $('genreFilter').innerHTML='<option value="">All genres</option>'+genres.map(g=>`<option value="${esc(g.toLowerCase())}">${esc(g)}</option>`).join('');
  if(genres.some(g=>g.toLowerCase()===current)) $('genreFilter').value=current;
}
async function loadMovies() {
  movies=await api('/api/movies');
  if(!movies.length){$('movieGrid').innerHTML='<p class="muted">No movies are available yet.</p>';return;}
  $('movieSelect').innerHTML=movies.map(m=>`<option value="${m.id}">${esc(m.title)}</option>`).join('');
  fillGenreFilter(); renderMovies();
  if(!movies.some(m=>m.id===activeMovie)) activeMovie=movies[0].id;
  await chooseMovie(activeMovie);
}
async function chooseMovie(id) {
  activeMovie=id; selected.clear(); renderMovies(); $('movieSelect').value=String(id);
  const showData=await api('/api/shows/'+id);
  $('showSelect').innerHTML=showData.map(s=>`<option value="${s.id}">${esc(s.theatre)} · ${esc(s.show_time)}</option>`).join('');
  currentShow=showData[0]?.id || null;
  $('showSelect').onchange=()=>{currentShow=+$('showSelect').value;selected.clear();refreshSeats();updateSummary();};
  await refreshSeats(); updateSummary();
}
async function refreshSeats() {
  if(!currentShow){$('seatGrid').innerHTML='<p class="muted">No showtime available. Please contact the cinema.</p>';return;}
  const seats=await api('/api/seats/'+currentShow);
  $('seatGrid').innerHTML=seats.map(s=>{
    const cls=s.status==='booked'?'booked':s.locked?'locked':selected.has(s.seat_code)?'selected':'';
    const disabled=s.status==='booked'||s.locked;
    return `<button class="seat ${cls}" data-seat="${esc(s.seat_code)}" ${disabled?'disabled':''}>${esc(s.seat_code)}</button>`;
  }).join('');
  $('seatGrid').querySelectorAll('.seat:not(:disabled)').forEach(b=>b.onclick=()=>{
    const seat=b.dataset.seat;
    if(selected.has(seat)) selected.delete(seat);
    else if(selected.size<10) selected.add(seat);
    else notice('You can select a maximum of 10 seats.',true);
    refreshSeats(); updateSummary();
  });
}
function updateSummary(){
  $('selectedCount').textContent=selected.size;
  $('selectedNames').textContent=selected.size?[...selected].sort().join(' · '):'No seats selected';
  $('total').textContent='₹'+selected.size*180;
}
$('movieSearch').addEventListener('input',renderMovies);
$('genreFilter').addEventListener('change',renderMovies);
$('movieSelect').addEventListener('change',()=>chooseMovie(+$('movieSelect').value));
$('bookBtn').onclick=async()=>{
  if(!selected.size){notice('Please select at least one seat.',true);return;}
  if(!$('customer').value.trim()){notice('Please enter your name.',true);return;}
  try{
    const result=await api('/api/book',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer:$('customer').value,show_id:currentShow,seats:[...selected]})});
    selected.clear();updateSummary();notice(`Confirmed! Booking ID: ${result.booking_id} · Total ₹${result.total}`);await refreshSeats();
  }catch(e){notice(e.message+' Refreshing seats…',true);selected.clear();updateSummary();await refreshSeats();}
};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function logLine(n,t){const p=document.createElement('p');p.innerHTML=`<b>${String(n).padStart(2,'0')}</b> ${esc(t)}`;$('log').appendChild(p);}
$('runSim').onclick=async()=>{
  $('runSim').disabled=true;$('log').innerHTML='';$('statusA').textContent='REQUESTING';$('statusB').textContent='WAITING';$('mutexState').textContent='LOCK: ACQUIRED BY A';
  logLine(1,'Customer A requests seats A1, A2, A3.');await wait(450);logLine(2,'Mutex acquired by Customer A. Entering critical section.');await wait(450);logLine(3,'Customer B requests A2, A3, A4 and must wait.');await wait(450);logLine(4,'A checks availability and atomically confirms all three seats.');$('statusA').textContent='CONFIRMED';await wait(450);logLine(5,'Customer A releases mutex.');$('mutexState').textContent='LOCK: RELEASED';await wait(350);$('mutexState').textContent='LOCK: ACQUIRED BY B';$('statusB').textContent='CHECKING';logLine(6,'Customer B enters critical section and rechecks availability.');await wait(450);logLine(7,'A2 and A3 are already booked. Customer B transaction is rejected.');$('statusB').textContent='REJECTED';$('mutexState').textContent='LOCK: RELEASED';logLine(8,'Mutex released. No duplicate booking occurred.');$('runSim').disabled=false;
};
$('resetSim').onclick=()=>{$('log').innerHTML='<p><b>01</b> Waiting for simulation...</p>';$('statusA').textContent='READY';$('statusB').textContent='READY';$('mutexState').textContent='LOCK: FREE';$('runSim').disabled=false;};
loadMovies().catch(e=>notice(e.message,true));
