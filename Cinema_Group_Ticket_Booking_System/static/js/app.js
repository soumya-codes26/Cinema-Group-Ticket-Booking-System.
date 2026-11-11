let movies=[], currentShow=null, selected=new Set(), activeMovie=null;
const $=id=>document.getElementById(id);
async function api(url,opts){const r=await fetch(url,opts);const d=await r.json();if(!r.ok)throw new Error(d.message||"Request failed");return d}
async function loadMovies(){
 movies=await api('/api/movies');
 $('movieGrid').innerHTML=movies.map(m=>`<article class="movie" data-id="${m.id}"><div class="poster" style="background-image:url('${m.poster}')"><span class="rating">★ ${m.rating}</span></div><div class="movie-info"><h3>${m.title}</h3><p>${m.genre} · ${m.duration}</p></div></article>`).join('');
 $('movieSelect').innerHTML=movies.map(m=>`<option value="${m.id}">${m.title}</option>`).join('');
 $('movieGrid').querySelectorAll('.movie').forEach(el=>el.onclick=()=>chooseMovie(+el.dataset.id));
 $('movieSelect').onchange=()=>chooseMovie(+$('movieSelect').value);
 await chooseMovie(movies[0].id);
}
async function chooseMovie(id){
 activeMovie=id;selected.clear();document.querySelectorAll('.movie').forEach(x=>x.classList.toggle('active',+x.dataset.id===id));$('movieSelect').value=id;
 const shows=await api('/api/shows/'+id);$('showSelect').innerHTML=shows.map(s=>`<option value="${s.id}">${s.theatre} · ${s.show_time}</option>`).join('');
 $('showSelect').onchange=()=>{currentShow=+$('showSelect').value;refreshSeats()};currentShow=shows[0]?.id;await refreshSeats();updateSummary();
}
async function refreshSeats(){
 if(!currentShow)return;const seats=await api('/api/seats/'+currentShow);
 $('seatGrid').innerHTML=seats.map(s=>{let cls=s.status==='booked'?'booked':s.locked?'locked':selected.has(s.seat_code)?'selected':'';let disabled=s.status==='booked'||s.locked;return `<button class="seat ${cls}" data-seat="${s.seat_code}" ${disabled?'disabled':''}>${s.seat_code}</button>`}).join('');
 $('seatGrid').querySelectorAll('.seat:not(:disabled)').forEach(b=>b.onclick=()=>{let seat=b.dataset.seat;if(selected.has(seat))selected.delete(seat);else if(selected.size<10)selected.add(seat);else showNotice('You can select a maximum of 10 seats.',true);refreshSeats();updateSummary()});
}
function updateSummary(){$('selectedCount').textContent=selected.size;$('selectedNames').textContent=selected.size?[...selected].sort().join(' · '):'No seats selected';$('total').textContent='₹'+selected.size*180}
function showNotice(msg,error=false){$('notice').textContent=msg;$('notice').style.color=error?'#f07187':'#45d6a0'}
$('bookBtn').onclick=async()=>{if(!selected.size){showNotice('Please select at least one seat.',true);return}if(!$('customer').value.trim()){showNotice('Please enter your name.',true);return}
 try{const result=await api('/api/book',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({customer:$('customer').value,show_id:currentShow,seats:[...selected]})});selected.clear();updateSummary();showNotice(`Confirmed! Booking ID: ${result.booking_id} · Total ₹${result.total}`);await refreshSeats()}catch(e){showNotice(e.message+' Refreshing seats…',true);selected.clear();updateSummary();await refreshSeats()}
};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
function logLine(n,t){const p=document.createElement('p');p.innerHTML=`<b>${String(n).padStart(2,'0')}</b> ${t}`;$('log').appendChild(p)}
$('runSim').onclick=async()=>{$('runSim').disabled=true;$('log').innerHTML='';$('statusA').textContent='REQUESTING';$('statusB').textContent='WAITING';$('mutexState').textContent='LOCK: ACQUIRED BY A';
logLine(1,'Customer A requests seats A1, A2, A3.');await wait(650);logLine(2,'Mutex acquired by Customer A. Entering critical section.');await wait(650);logLine(3,'Customer B requests A2, A3, A4 and must wait.');await wait(650);logLine(4,'A checks availability and atomically confirms all three seats.');$('statusA').textContent='CONFIRMED';await wait(650);logLine(5,'Customer A releases mutex.');$('mutexState').textContent='LOCK: RELEASED';await wait(500);$('mutexState').textContent='LOCK: ACQUIRED BY B';$('statusB').textContent='CHECKING';logLine(6,'Customer B enters critical section and rechecks availability.');await wait(650);logLine(7,'A2 and A3 are already booked. Customer B transaction is rejected.');$('statusB').textContent='REJECTED';$('mutexState').textContent='LOCK: RELEASED';logLine(8,'Mutex released. No duplicate booking occurred.');$('runSim').disabled=false};
$('resetSim').onclick=()=>{$('log').innerHTML='<p><b>01</b> Waiting for simulation...</p>';$('statusA').textContent='READY';$('statusB').textContent='READY';$('mutexState').textContent='LOCK: FREE';$('runSim').disabled=false};
loadMovies().catch(e=>showNotice(e.message,true));
