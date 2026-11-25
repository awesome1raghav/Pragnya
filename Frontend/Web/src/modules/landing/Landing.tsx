'use client';

/* NEXTRON landing. One idea carried down the page: an ordinary frame becomes an evidence exhibit.
   1 Hero: the apparent image, and the visitor's own examination of it (Exhibit).
   2 The contradiction: the copied group, side by side with its source and their difference.
   3 The investigation: how a finding stays tied to its source evidence.
   4 The limits: what the example proves and what it does not.
   5 The action: the demo workspace.
   Motion: one entrance, reveals on first view, and the exhibit's own controlled transitions. Nothing loops. */
import { useRef, useState } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { Aperture, ArrowRight, ArrowUpRight, Menu, X } from 'lucide-react';
import Exhibit from './Exhibit';
import { Clue, FinalCta, Investigation, Limits } from './Sections';
import s from './landing.module.css';

gsap.registerPlugin(ScrollTrigger);

export default function Landing() {
  const root = useRef<HTMLElement>(null);
  const [menu, setMenu] = useState(false);

  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      // starting states are set in CSS (html.js), so nothing flashes before this runs
      gsap.timeline({ defaults: { ease: 'expo.out' } })
        .fromTo('[data-nav] > *', { y: -12, opacity: 0 }, { y: 0, opacity: 1, duration: .8, stagger: .06 })
        .fromTo('[data-line]', { yPercent: 105, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 1.1, stagger: .09 }, .1)
        .fromTo('[data-enter-frame]', { opacity: 0, y: 28 }, { opacity: 1, y: 0, duration: 1.3, clearProps: 'transform' }, .2)
        .fromTo('[data-enter]', { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: .9, stagger: .07, clearProps: 'transform' }, .55);

      gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach(el => {
        gsap.from(el.querySelectorAll('[data-reveal-item]'), { y: 26, opacity: 0, duration: .9, stagger: .08, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 82%', once: true } });
      });
    });
    return () => mm.revert();
  }, { scope: root });

  const close = () => setMenu(false);

  return <main ref={root} className={s.landing}>
    <a className={s.skip} href='#main-content'>Skip to content</a>
    <header className={`${s.header} ${s.wrap}`} data-nav>
      <Link href='/' className={s.brand} aria-label='NEXTRON home'><Aperture aria-hidden='true' /><span>NEXTRON</span></Link>
      <nav aria-label='Main navigation' className={`${s.nav} ${menu ? s.openNav : ''}`}>
        <a href='#clue' onClick={close}>Technology</a><a href='#how-it-works' onClick={close}>How it works</a><a href='#research' onClick={close}>Research</a>
      </nav>
      <Link href='/dashboard' className={s.launch}><span className={s.long}>Launch analyzer</span><span className={s.short}>Analyze</span> <ArrowUpRight size={18} /></Link>
      <button className={s.menuButton} onClick={() => setMenu(!menu)} aria-expanded={menu} aria-label={menu ? 'Close navigation' : 'Open navigation'}>{menu ? <X /> : <Menu />}</button>
    </header>

    <section id='main-content' className={`${s.hero} ${s.wrap}`} aria-labelledby='hero-title'>
      <div className={s.heroCopy}>
        <p className={s.eyebrow} data-enter><i />Digital media forensics</p>
        <h1 id='hero-title'><span className={s.mask}><span data-line>Seeing isn’t</span></span><span className={s.mask}><span data-line>believing<em>.</em></span></span></h1>
        <p className={s.heroLead} data-enter>NEXTRON investigates manipulated photos and video, and shows you the pixels that prove it.</p>
        <div className={s.actions} data-enter>
          <Link className={s.primary} href='/dashboard'>Analyze media <ArrowRight size={20} /></Link>
          <a href='#clue' className={s.textLink}>Read the evidence</a>
        </div>
      </div>
      <div className={s.heroExhibit}><Exhibit /></div>
    </section>

    <Clue />
    <Investigation />
    <Limits />
    <FinalCta />

    <footer className={`${s.footer} ${s.wrap}`}>
      <div className={s.footBrand}><Aperture size={24} /><b>NEXTRON</b><span>Digital media verification</span></div>
      <Link href='/dashboard' className={s.launch}>Launch analyzer <ArrowUpRight size={18} /></Link>
      <p>AAROHAN 2.0 · Gokaraju Rangaraju Institute of Engineering and Technology</p>
      <p>Raghavendra Suddula · Ashok Choudhary · Hima Charan Naga Sai Sathwik Kasturi · Nilesh Eligeti</p>
      <p>Exhibit photograph: Nicolai Berntsen (Unsplash License), with an edit staged by the NEXTRON team. Graph thumbnails: Unsplash and Wikimedia Commons contributors, credited in the workspace.</p>
    </footer>
  </main>;
}
