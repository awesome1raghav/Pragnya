'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { Aperture, ArrowRight, ArrowUpRight, Layers3, Clock3, AudioLines, Menu, X, Check } from 'lucide-react';
import AnalysisConsole from './console';
import WaveField from './wave-field';
import { Dissection, FinalCta, GraphShowcase, Statement } from './landing-sections';
import { whenReady } from './ready';
import s from './landing.module.css';

gsap.registerPlugin(ScrollTrigger);

const capabilities = [
  [Layers3, 'Spatial Analysis', 'Detects visual inconsistencies, artifacts and unnatural patterns.'],
  [Clock3, 'Temporal Analysis', 'Finds frame-level anomalies, transitions and irregular motion.'],
  [AudioLines, 'Audio-Visual Analysis', 'Checks lip-sync, audio alignment and cross-media consistency.'],
] as const;

export default function Landing() {
  const root = useRef<HTMLElement>(null);
  const [reduced, setReduced] = useState(false);
  const [mode, setMode] = useState(0);
  const [menu, setMenu] = useState(false);
  const [motionRunning, setMotionRunning] = useState(true);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(preference.matches);
    update();
    preference.addEventListener('change', update);
    return () => preference.removeEventListener('change', update);
  }, []);

  // entrance + section reveals
  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      // built now (so everything starts hidden under the loader), played when the loader hands over
      const tl = gsap.timeline({ paused: true, defaults: { ease: 'expo.out' } });
      const stop = whenReady(() => tl.play());
      tl.from('[data-nav] > *', { y: -14, opacity: 0, duration: .8, stagger: .06 })
        .from('[data-eyebrow-line]', { scaleX: 0, transformOrigin: 'left', duration: .9 }, .15)
        .from('[data-eyebrow-text]', { opacity: 0, x: -10, duration: .7 }, .25)
        .from('[data-line]', { yPercent: 110, duration: 1, stagger: .1 }, .2)
        .from('[data-intro]', { y: 18, opacity: 0, duration: .8, stagger: .08 }, .55)
        .from('[data-console]', { y: 40, opacity: 0, duration: 1.3, clearProps: 'transform,opacity' }, .3)
        .from('[data-rail] > *', { x: -12, opacity: 0, duration: .6, stagger: .07, clearProps: 'transform,opacity' }, .9)
        .from('canvas', { opacity: 0, duration: 2, ease: 'power2.out' }, .4);

      gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((el) => {
        gsap.from(el.querySelectorAll('[data-reveal-item]'), {
          y: 28, opacity: 0, duration: .9, stagger: .09, ease: 'expo.out',
          scrollTrigger: { trigger: el, start: 'top 85%', once: true },
        });
      });
      gsap.utils.toArray<HTMLElement>('[data-rule]').forEach((el) => {
        gsap.from(el, { scaleX: 0, transformOrigin: 'left', duration: 1.4, ease: 'expo.out', scrollTrigger: { trigger: el, start: 'top 95%', once: true } });
      });
      return () => stop();
    });
    return () => mm.revert();
  }, { scope: root });

  const go = (i: number) => { setMode(i); root.current?.querySelector('#main-content')?.scrollIntoView({ behavior: reduced ? 'instant' : 'smooth' }); };

  return <main ref={root} className={s.landing} data-still={!motionRunning || reduced || undefined}>
    <a className={s.skip} href='#main-content'>Skip to content</a>
    <header className={`${s.header} ${s.wrap}`} data-nav>
      <Link href='/' className={s.brand} aria-label='NEXTRON home'><Aperture aria-hidden='true' /><span>NEXTRON</span></Link>
      <nav aria-label='Main navigation' className={`${s.nav} ${menu ? s.openNav : ''}`}>
        <a href='#technology' onClick={() => setMenu(false)}>Technology</a><a href='#how-it-works' onClick={() => setMenu(false)}>How it works</a><a href='#research' onClick={() => setMenu(false)}>Research</a>
      </nav>
      <Link href='/workspace' className={s.launch}>Launch analyzer <ArrowUpRight size={18} /></Link>
      <button className={s.menuButton} onClick={() => setMenu(!menu)} aria-expanded={menu} aria-label={menu ? 'Close navigation' : 'Open navigation'}>{menu ? <X /> : <Menu />}</button>
    </header>

    <section id='main-content' className={`${s.hero} ${s.wrap}`} aria-labelledby='hero-title'>
      <div className={s.heroCopy}>
        <p className={s.eyebrow}><i data-eyebrow-line /><span data-eyebrow-text>Digital media forensics / 01</span></p>
        <h1 id='hero-title'><span className={s.mask}><span data-line>Seeing isn’t</span></span><span className={s.mask}><span data-line>believing<em>.</em></span></span></h1>
        <p data-intro className={s.heroLead}>Investigate manipulated media.<br />Find the evidence, frame by frame.</p>
        <div data-intro className={s.actions}><Link className={s.primary} href='/workspace'>Analyze Media <ArrowRight size={20} /></Link><a href='#technology' className={s.textLink}>Explore the technology</a></div>
      </div>

      <div className={s.stageWrap}>
        <AnalysisConsole mode={mode} setMode={setMode} reduced={reduced} running={motionRunning} setRunning={setMotionRunning} />
      </div>
      <WaveField className={s.waveField} running={motionRunning} reduced={reduced} />
    </section>

    <section id='technology' className={`${s.capabilities} ${s.wrap}`} aria-labelledby='capability-title' data-reveal>
      <i className={s.rule} data-rule aria-hidden='true' />
      <h2 id='capability-title' data-reveal-item><span aria-hidden='true' />Evidence, not just <br />a verdict.</h2>
      {capabilities.map(([Glyph, title, body], i) => <button key={title} data-reveal-item onClick={() => go(i)}><Glyph size={28} strokeWidth={1.6} /><h3>{title}</h3><p>{body}</p><ArrowUpRight className={s.capArrow} size={18} /></button>)}
    </section>

    <Dissection />
    <Statement />
    <GraphShowcase />

    <section className={`${s.research} ${s.wrap}`} id='research' data-reveal>
      <div>
        <p className={s.eyebrow} data-reveal-item><i /><span>Research & methodology / 04</span></p>
        <h2 data-reveal-item>A conclusion should <br />withstand a closer look.</h2>
        <p data-reveal-item>The system combines manipulation-type identification, region and timestamp localization, and cross-signal correlation. When evidence is insufficient or conflicts, the assessment stays inconclusive.</p>
        <div className={s.researchTags} data-reveal-item><span><Check size={16} /> Explicit uncertainty</span><span><Check size={16} /> Traceable findings</span></div>
      </div>
      <div className={s.researchRows}>
        {[['Detection & localization', 'Face swap, facial reenactment, lip-sync edits, synthetic video and partial splices.'], ['Evidence fusion', 'Score calibration, evidence agreement and conflict handling across the three branches.'], ['Research foundations', 'FaceForensics++, DFDC and Deepfake-Eval-2024 inform the direction. Product benchmarks are not yet published.']].map(([h, p], i) => <article key={h} data-reveal-item><span>0{i + 1}</span><div><h3>{h}</h3><p>{p}</p></div></article>)}
      </div>
    </section>

    <FinalCta />

    <footer className={`${s.footer} ${s.wrap}`} data-reveal>
      <div className={s.footBrand} data-reveal-item><Aperture size={24} /><b>NEXTRON</b><span>Digital media verification</span></div>
      <Link href='/workspace' className={s.launch} data-reveal-item>Launch analyzer <ArrowUpRight size={18} /></Link>
      <p data-reveal-item>AAROHAN 2.0 · Gokaraju Rangaraju Institute of Engineering and Technology</p>
      <p data-reveal-item>Raghavendra Suddula · Ashok Choudhary · Hima Charan Naga Sai Sathwik Kasturi · Nilesh Eligeti</p>
    </footer>
  </main>;
}
