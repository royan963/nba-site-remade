import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { enc } from '../api/client';

/** Compact "ask the stats" box in the header; opens /search. */
export function HeaderSearch() {
  const [text, setText] = useState('');
  const navigate = useNavigate();
  return (
    <form className="header-search" role="search" onSubmit={e => { e.preventDefault(); if (text.trim()) { navigate(`/search?q=${enc(text.trim())}`); setText(''); } }}>
      <input type="search" id="header-search" value={text} onChange={e => setText(e.target.value)}
             placeholder="Ask: best rebounding guards of the 90s" aria-label="Search players and stats" />
    </form>
  );
}
