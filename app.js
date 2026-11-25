const playButton = document.querySelector('.video-play');
playButton?.addEventListener('click', () => {
  const isPaused = playButton.textContent === '▶';
  playButton.textContent = isPaused ? 'Ⅱ' : '▶';
  playButton.setAttribute('aria-label', isPaused ? 'Pause media' : 'Play media');
});
