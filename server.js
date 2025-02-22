// server.js
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// Mevcut savaş oturumu bilgileri
let currentBattle = {
  inProgress: false,    // Savaş başladı mı?
  joinDeadline: null,   // Katılım süresinin bitiş zamanı
  participants: []      // Katılan oyuncuların socket ID'leri
};

// Bağlanan her istemci için olaylar
io.on('connection', (socket) => {
  console.log('Yeni oyuncu bağlandı: ' + socket.id);

  // Savaş başlatma isteği (örn. bir yönetici ya da oyuncu tarafından)
  socket.on('startBattle', () => {
    if (currentBattle.inProgress) {
      socket.emit('message', 'Savaş zaten devam ediyor.');
      return;
    }
    console.log('Savaş başlatılıyor. 30 saniye içinde katılım sağlanacak.');
    // Savaş oturumunu sıfırla
    currentBattle = {
      inProgress: false,
      joinDeadline: Date.now() + 30000, // 30 saniye sonrasına ayarla
      participants: []
    };
    // Tüm oyunculara katılım penceresinin açıldığını bildir
    io.emit('battleStatus', { status: 'waiting', joinDeadline: currentBattle.joinDeadline });
    
    // 30 saniye sonra katılım penceresini kapatıp savaşı başlat
    setTimeout(() => {
      currentBattle.inProgress = true;
      io.emit('battleStatus', { status: 'started', participants: currentBattle.participants });
      console.log('Savaş başladı. Katılımcılar:', currentBattle.participants);
      
      // Savaş süresi örneğin 30 saniye olsun; sonra savaş biter.
      setTimeout(() => {
        currentBattle.inProgress = false;
        io.emit('battleStatus', { status: 'ended' });
        console.log('Savaş sona erdi.');
      }, 30000);
    }, 30000);
  });

  // Oyuncunun savaşa katılma isteği
  socket.on('joinBattle', () => {
    if (!currentBattle.joinDeadline) {
      socket.emit('message', 'Şu anda katılım penceresi açık değil.');
      return;
    }
    if (currentBattle.inProgress) {
      socket.emit('message', 'Savaş başladı, lütfen bir sonraki savaşa katılın.');
      return;
    }
    if (Date.now() > currentBattle.joinDeadline) {
      socket.emit('message', 'Katılım süresi doldu, lütfen bir sonraki savaşı bekleyin.');
      return;
    }
    // Aynı oyuncunun birden fazla katılmasını engelle
    if (!currentBattle.participants.includes(socket.id)) {
      currentBattle.participants.push(socket.id);
      socket.emit('message', 'Savaşa katıldınız.');
      io.emit('battleStatus', { status: 'waiting', participants: currentBattle.participants });
    } else {
      socket.emit('message', 'Zaten katıldınız.');
    }
  });

  // Oyuncu bağlantısı kesildiğinde
  socket.on('disconnect', () => {
    console.log('Oyuncu ayrıldı: ' + socket.id);
    if (currentBattle.participants) {
      currentBattle.participants = currentBattle.participants.filter(id => id !== socket.id);
    }
  });
});

// Client dosyalarını 'public' klasöründen sun
app.use(express.static('public'));

server.listen(3000, () => {
  console.log('Sunucu 3000 portunda çalışıyor.');
});
