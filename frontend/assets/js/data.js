/**
 * StudySpace — demo fixtures.
 *
 * These records power the static preview when the Django API is not reachable
 * (GitHub Pages, local `python -m http.server`, offline). They are illustrative
 * sample data, not real students or real faculty.
 */

export const CATEGORIES = [
  { id: 'class-10',  label: 'Class 10',    sub: 'Boards',      icon: 'book',   glyph: 'X' },
  { id: 'class-12',  label: 'Class 12',    sub: 'Boards',      icon: 'cap',    glyph: 'XII' },
  { id: 'jee',       label: 'JEE',         sub: 'Main + Adv',  icon: 'atom',   glyph: 'JEE' },
  { id: 'neet',      label: 'NEET',        sub: 'Medical',     icon: 'heart',  glyph: 'NEET' },
  { id: 'upsc',      label: 'UPSC',        sub: 'Civil services', icon: 'shield', glyph: 'IAS' },
  { id: 'ssc',       label: 'SSC & Banking', sub: 'Govt exams', icon: 'brief',  glyph: 'SSC' },
  { id: 'gate',      label: 'GATE',        sub: 'Engineering', icon: 'cpu',    glyph: 'GATE' },
  { id: 'cuet',      label: 'CUET',        sub: 'University',  icon: 'building', glyph: 'CUET' }
];

export const COURSES = [
  {
    id: 1,
    slug: 'jee-main-2027-complete',
    title: 'JEE Main 2027 — Complete Physics, Chemistry & Maths',
    subject: 'Physics',
    exam: 'JEE',
    description:
      'A full-year live batch covering the entire JEE Main syllabus with daily practice problems, weekly tests and doubt sessions. Built for students starting their Class 12 preparation.',
    faculty: [
      { name: 'Dr. Aarav Menon', role: 'Physics', initials: 'AM', tone: 'violet' },
      { name: 'Ritika Sharma', role: 'Chemistry', initials: 'RS', tone: 'teal' },
      { name: 'Nikhil Rao', role: 'Mathematics', initials: 'NR', tone: 'amber' }
    ],
    rating: 4.8,
    ratingCount: 2841,
    learners: 18420,
    language: 'Hinglish',
    startsOn: '2026-11-04',
    durationMonths: 12,
    lessons: 486,
    tests: 62,
    pricing_mode: 'paid',
    price: 4499,
    mrp: 12999,
    badge: 'live',
    rank: 1
  },
  {
    id: 2,
    slug: 'neet-2027-biology-intensive',
    title: 'NEET 2027 — Biology Intensive with NCERT Mastery',
    subject: 'Biology',
    exam: 'NEET',
    description:
      'Line-by-line NCERT coverage, diagram-based revision and 4,000+ practice questions. Includes weekly full-length mocks with All-India percentile.',
    faculty: [
      { name: 'Dr. Sneha Kulkarni', role: 'Biology', initials: 'SK', tone: 'rose' },
      { name: 'Vivek Iyer', role: 'Chemistry', initials: 'VI', tone: 'teal' }
    ],
    rating: 4.9,
    ratingCount: 3910,
    learners: 24380,
    language: 'Hinglish',
    startsOn: '2026-11-11',
    durationMonths: 11,
    lessons: 412,
    tests: 48,
    pricing_mode: 'paid',
    price: 3999,
    mrp: 10999,
    badge: 'bestseller',
    rank: 2
  },
  {
    id: 3,
    slug: 'class-10-science-foundation',
    title: 'Class 10 Science & Maths — Board Foundation',
    subject: 'Science',
    exam: 'Class 10',
    description:
      'Board-focused course with chapter tests, previous-year questions and revision notes. Free to start, no access code required.',
    faculty: [{ name: 'Pooja Deshmukh', role: 'Science', initials: 'PD', tone: 'violet' }],
    rating: 4.7,
    ratingCount: 1204,
    learners: 31200,
    language: 'Hindi + English',
    startsOn: '2026-10-28',
    durationMonths: 8,
    lessons: 268,
    tests: 34,
    pricing_mode: 'free',
    price: 0,
    mrp: 0,
    badge: 'free',
    rank: 3
  },
  {
    id: 4,
    slug: 'ssc-cgl-2026-foundation',
    title: 'SSC CGL 2026 — Quant, Reasoning & English Foundation',
    subject: 'Reasoning',
    exam: 'SSC',
    description:
      'Exam-pattern practice with sectional timers, previous-year papers from 2018–2025 and a full All-India rank after every mock.',
    faculty: [
      { name: 'Rahul Bhatia', role: 'Quantitative Aptitude', initials: 'RB', tone: 'amber' },
      { name: 'Ananya Pillai', role: 'Reasoning', initials: 'AP', tone: 'ink' }
    ],
    rating: 4.6,
    ratingCount: 1876,
    learners: 15980,
    language: 'Hinglish',
    startsOn: '2026-11-18',
    durationMonths: 7,
    lessons: 322,
    tests: 54,
    pricing_mode: 'paid',
    price: 2499,
    mrp: 7999,
    badge: 'new',
    rank: 4
  },
  {
    id: 5,
    slug: 'upsc-prelims-2027-gs',
    title: 'UPSC Prelims 2027 — General Studies Complete',
    subject: 'General Studies',
    exam: 'UPSC',
    description:
      'Polity, economy, geography, environment and current affairs in one structured track, with a daily current-affairs brief and 30 sectional tests.',
    faculty: [{ name: 'Karthik Subramanian', role: 'Polity & Economy', initials: 'KS', tone: 'ink' }],
    rating: 4.8,
    ratingCount: 967,
    learners: 8140,
    language: 'English',
    startsOn: '2026-12-02',
    durationMonths: 10,
    lessons: 356,
    tests: 41,
    pricing_mode: 'paid',
    price: 5999,
    mrp: 15999,
    badge: 'live',
    rank: 5
  },
  {
    id: 6,
    slug: 'gate-cs-2027',
    title: 'GATE CS 2027 — Computer Science Crash Track',
    subject: 'Computer Science',
    exam: 'GATE',
    description:
      'Data structures, algorithms, operating systems, DBMS and theory of computation, taught with worked GATE questions from the last 12 years.',
    faculty: [{ name: 'Meera Krishnan', role: 'Computer Science', initials: 'MK', tone: 'teal' }],
    rating: 4.7,
    ratingCount: 742,
    learners: 6210,
    language: 'English',
    startsOn: '2026-11-25',
    durationMonths: 6,
    lessons: 214,
    tests: 28,
    pricing_mode: 'paid',
    price: 3499,
    mrp: 8999,
    badge: null,
    rank: 6
  },
  {
    id: 7,
    slug: 'jee-advanced-2027-crash',
    title: 'JEE Advanced 2027 — Paper 1 & 2 Crash Course',
    subject: 'Mathematics',
    exam: 'JEE',
    description:
      'Problem-solving intensive for JEE Advanced: multi-concept questions, previous-year papers from 2015–2026 and a timed paper every Sunday with a detailed solution walkthrough.',
    faculty: [
      { name: 'Aditya Narayan', role: 'Mathematics', initials: 'AN', tone: 'amber' },
      { name: 'Shreya Bose', role: 'Physics', initials: 'SB', tone: 'violet' }
    ],
    rating: 4.9,
    ratingCount: 1320,
    learners: 9240,
    language: 'English',
    startsOn: '2026-12-10',
    durationMonths: 4,
    lessons: 268,
    tests: 40,
    pricing_mode: 'paid',
    price: 6999,
    mrp: 19999,
    badge: 'live',
    rank: 7
  },
  {
    id: 8,
    slug: 'neet-2027-physics-chemistry',
    title: 'NEET 2027 — Physics & Chemistry Booster',
    subject: 'Chemistry',
    exam: 'NEET',
    description:
      'Formula-first revision for Physics and Chemistry with 1,800 NCERT-anchored questions, weekly sectional tests and a mistake log that tracks every weak chapter.',
    faculty: [
      { name: 'Vivek Iyer', role: 'Chemistry', initials: 'VI', tone: 'teal' },
      { name: 'Neha Saxena', role: 'Physics', initials: 'NS', tone: 'rose' }
    ],
    rating: 4.8,
    ratingCount: 2210,
    learners: 16780,
    language: 'Hinglish',
    startsOn: '2026-11-09',
    durationMonths: 9,
    lessons: 356,
    tests: 46,
    pricing_mode: 'paid',
    price: 3299,
    mrp: 9499,
    badge: 'bestseller',
    rank: 8
  },
  {
    id: 9,
    slug: 'class-12-physics-boards',
    title: 'Class 12 Physics — Board Exam Revision',
    subject: 'Physics',
    exam: 'Class 12',
    description:
      'Chapter-wise revision aligned to the CBSE syllabus, with derivations written out step by step, numericals from the last ten board papers and a final pre-board mock.',
    faculty: [{ name: 'Pooja Deshmukh', role: 'Physics', initials: 'PD', tone: 'violet' }],
    rating: 4.7,
    ratingCount: 864,
    learners: 12460,
    language: 'Hindi + English',
    startsOn: '2026-11-02',
    durationMonths: 6,
    lessons: 182,
    tests: 24,
    pricing_mode: 'free',
    price: 0,
    mrp: 0,
    badge: 'free',
    rank: 9
  },
  {
    id: 10,
    slug: 'cuet-2027-general-test',
    title: 'CUET 2027 — General Test & Reasoning',
    subject: 'Reasoning',
    exam: 'CUET',
    description:
      'Quantitative aptitude, logical reasoning and general awareness for the CUET General Test, with sectional drills and eight full-length mocks.',
    faculty: [{ name: 'Ananya Pillai', role: 'Reasoning', initials: 'AP', tone: 'ink' }],
    rating: 4.5,
    ratingCount: 438,
    learners: 5310,
    language: 'English',
    startsOn: '2026-12-18',
    durationMonths: 5,
    lessons: 168,
    tests: 20,
    pricing_mode: 'paid',
    price: 1499,
    mrp: 4999,
    badge: 'new',
    rank: 10
  },
  {
    id: 11,
    slug: 'ssc-chsl-2027-complete',
    title: 'SSC CHSL 2027 — Quant, Reasoning & English',
    subject: 'Mathematics',
    exam: 'SSC',
    description:
      'Tier 1 and Tier 2 preparation with typing practice notes, previous-year papers from 2016–2025 and daily 20-question practice sets.',
    faculty: [
      { name: 'Rahul Bhatia', role: 'Quantitative Aptitude', initials: 'RB', tone: 'amber' },
      { name: 'Sana Qureshi', role: 'English', initials: 'SQ', tone: 'teal' }
    ],
    rating: 4.6,
    ratingCount: 1102,
    learners: 9870,
    language: 'Hinglish',
    startsOn: '2026-11-22',
    durationMonths: 6,
    lessons: 244,
    tests: 38,
    pricing_mode: 'paid',
    price: 1999,
    mrp: 5999,
    badge: 'new',
    rank: 11
  },
  {
    id: 12,
    slug: 'upsc-mains-2027-essay',
    title: 'UPSC Mains 2027 — Essay & Ethics',
    subject: 'General Studies',
    exam: 'UPSC',
    description:
      'Essay structuring, ethics case studies and answer-writing practice with two evaluated answers a week and examiner-style feedback notes.',
    faculty: [{ name: 'Karthik Subramanian', role: 'Essay & Ethics', initials: 'KS', tone: 'ink' }],
    rating: 4.7,
    ratingCount: 512,
    learners: 4180,
    language: 'English',
    startsOn: '2026-12-06',
    durationMonths: 8,
    lessons: 148,
    tests: 16,
    pricing_mode: 'paid',
    price: 4999,
    mrp: 12999,
    badge: null,
    rank: 12
  },
  {
    id: 13,
    slug: 'gate-me-2027',
    title: 'GATE ME 2027 — Mechanical Engineering',
    subject: 'Mathematics',
    exam: 'GATE',
    description:
      'Engineering mathematics, thermodynamics, fluid mechanics and design, taught with 15 years of GATE questions and a topic-wise strength report after each test.',
    faculty: [{ name: 'Meera Krishnan', role: 'Engineering Mathematics', initials: 'MK', tone: 'teal' }],
    rating: 4.6,
    ratingCount: 389,
    learners: 3420,
    language: 'English',
    startsOn: '2026-11-16',
    durationMonths: 7,
    lessons: 226,
    tests: 30,
    pricing_mode: 'paid',
    price: 3999,
    mrp: 9999,
    badge: null,
    rank: 13
  },
  {
    id: 14,
    slug: 'class-10-maths-intensive',
    title: 'Class 10 Maths — Intensive Practice',
    subject: 'Mathematics',
    exam: 'Class 10',
    description:
      'Every chapter from real numbers to probability, with 40 practice questions per chapter and a board-pattern mock every fortnight.',
    faculty: [{ name: 'Pooja Deshmukh', role: 'Mathematics', initials: 'PD', tone: 'violet' }],
    rating: 4.8,
    ratingCount: 1508,
    learners: 18640,
    language: 'Hindi + English',
    startsOn: '2026-10-30',
    durationMonths: 6,
    lessons: 196,
    tests: 28,
    pricing_mode: 'free',
    price: 0,
    mrp: 0,
    badge: 'free',
    rank: 14
  },
  {
    id: 15,
    slug: 'english-grammar-ssc',
    title: 'English Grammar for SSC & Banking',
    subject: 'English',
    exam: 'SSC',
    description:
      'Grammar rules, error spotting, cloze tests and vocabulary, with a daily 15-minute drill and weekly sectional tests.',
    faculty: [{ name: 'Sana Qureshi', role: 'English', initials: 'SQ', tone: 'teal' }],
    rating: 4.5,
    ratingCount: 706,
    learners: 7420,
    language: 'Hinglish',
    startsOn: '2026-11-27',
    durationMonths: 4,
    lessons: 132,
    tests: 18,
    pricing_mode: 'paid',
    price: 999,
    mrp: 2999,
    badge: null,
    rank: 15
  }
];

export const TESTS = [
  {
    id: 1,
    title: 'JEE Main Full Mock #12 — All India',
    exam: 'JEE',
    kind: 'Full mock',
    questions: 90,
    duration: 180,
    attempts: 12480,
    startsAt: '2026-10-26T14:00:00+05:30',
    price: 0,
    badge: 'live'
  },
  {
    id: 2,
    title: 'NEET Biology Sectional — Genetics & Evolution',
    exam: 'NEET',
    kind: 'Sectional',
    questions: 45,
    duration: 50,
    attempts: 8620,
    startsAt: '2026-10-25T10:00:00+05:30',
    price: 0,
    badge: 'live'
  },
  {
    id: 3,
    title: 'SSC CGL Tier 1 — Previous Year 2024',
    exam: 'SSC',
    kind: 'Previous year',
    questions: 100,
    duration: 60,
    attempts: 21430,
    startsAt: '2026-10-28T09:00:00+05:30',
    price: 0,
    badge: null
  },
  {
    id: 4,
    title: 'UPSC Prelims GS Paper 1 — Open Mock',
    exam: 'UPSC',
    kind: 'Full mock',
    questions: 100,
    duration: 120,
    attempts: 5240,
    startsAt: '2026-11-01T09:30:00+05:30',
    price: 99,
    badge: 'new'
  },
  {
    id: 5,
    title: 'Class 10 Science — Chapter Test: Light',
    exam: 'Class 10',
    kind: 'Chapter test',
    questions: 25,
    duration: 30,
    attempts: 18640,
    startsAt: '2026-10-24T18:00:00+05:30',
    price: 0,
    badge: null
  },
  {
    id: 6,
    title: 'GATE CS — Operating Systems Sectional',
    exam: 'GATE',
    kind: 'Sectional',
    questions: 30,
    duration: 45,
    attempts: 3180,
    startsAt: '2026-11-05T19:00:00+05:30',
    price: 0,
    badge: null
  },
  {
    id: 7,
    title: 'JEE Advanced Paper 1 — Full Mock',
    exam: 'JEE',
    kind: 'Full mock',
    questions: 54,
    duration: 180,
    attempts: 6820,
    startsAt: '2026-11-08T09:00:00+05:30',
    price: 149,
    badge: 'new'
  },
  {
    id: 8,
    title: 'NEET Full Mock #9 — All India',
    exam: 'NEET',
    kind: 'Full mock',
    questions: 180,
    duration: 200,
    attempts: 18960,
    startsAt: '2026-10-27T14:00:00+05:30',
    price: 0,
    badge: 'live'
  },
  {
    id: 9,
    title: 'Class 12 Physics — Chapter Test: Optics',
    exam: 'Class 12',
    kind: 'Chapter test',
    questions: 30,
    duration: 40,
    attempts: 7340,
    startsAt: '2026-10-29T18:00:00+05:30',
    price: 0,
    badge: null
  },
  {
    id: 10,
    title: 'CUET General Test — Sectional: Reasoning',
    exam: 'CUET',
    kind: 'Sectional',
    questions: 40,
    duration: 45,
    attempts: 2910,
    startsAt: '2026-11-02T17:00:00+05:30',
    price: 0,
    badge: null
  },
  {
    id: 11,
    title: 'SSC CHSL Tier 1 — Previous Year 2025',
    exam: 'SSC',
    kind: 'Previous year',
    questions: 100,
    duration: 60,
    attempts: 16280,
    startsAt: '2026-11-04T09:00:00+05:30',
    price: 0,
    badge: 'bestseller'
  },
  {
    id: 12,
    title: 'UPSC CSAT — Sectional: Data Interpretation',
    exam: 'UPSC',
    kind: 'Sectional',
    questions: 40,
    duration: 50,
    attempts: 3610,
    startsAt: '2026-11-07T10:30:00+05:30',
    price: 49,
    badge: null
  }
];

/** Questions used by the exam interface demonstration. */
export const EXAM_QUESTIONS = [
  {
    id: 1,
    type: 'single',
    section: 'Physics',
    marks: 4,
    negative: 1,
    prompt: 'A body of mass 2 kg moves with a velocity of 3 m/s. What is its kinetic energy?',
    options: ['4.5 J', '9 J', '18 J', '36 J'],
    answer: 1,
    explanation:
      'Kinetic energy is ½mv². Substituting m = 2 kg and v = 3 m/s gives ½ × 2 × 9 = 9 J.'
  },
  {
    id: 2,
    type: 'single',
    section: 'Physics',
    marks: 4,
    negative: 1,
    prompt:
      'A block slides down a frictionless incline of angle 30°. If g = 10 m/s², what is its acceleration along the incline?',
    options: ['2.5 m/s²', '5 m/s²', '8.7 m/s²', '10 m/s²'],
    answer: 1,
    explanation: 'The component of gravity along the incline is g·sinθ = 10 × 0.5 = 5 m/s².'
  },
  {
    id: 3,
    type: 'single',
    section: 'Physics',
    marks: 4,
    negative: 1,
    prompt: 'The SI unit of electric flux is:',
    options: ['N·m²/C', 'V/m', 'C/m²', 'N/C'],
    answer: 0,
    explanation: 'Electric flux Φ = E·A, so the unit is (N/C)·m² = N·m²/C.'
  },
  {
    id: 4,
    type: 'single',
    section: 'Chemistry',
    marks: 4,
    negative: 1,
    prompt: 'Which of the following has the highest first ionisation enthalpy?',
    options: ['Na', 'Mg', 'Al', 'Si'],
    answer: 3,
    explanation:
      'Ionisation enthalpy generally increases across a period. Silicon, being furthest right among the options, has the highest value.'
  },
  {
    id: 5,
    type: 'single',
    section: 'Chemistry',
    marks: 4,
    negative: 1,
    prompt: 'The hybridisation of carbon in ethyne (C₂H₂) is:',
    options: ['sp³', 'sp²', 'sp', 'sp³d'],
    answer: 2,
    explanation: 'Each carbon in ethyne forms two sigma bonds and two pi bonds, giving sp hybridisation.'
  },
  {
    id: 6,
    type: 'single',
    section: 'Chemistry',
    marks: 4,
    negative: 1,
    prompt: 'Which reagent converts an aldehyde into a carboxylic acid?',
    options: ['LiAlH₄', 'Tollens’ reagent', 'NaBH₄', 'Zn-Hg/HCl'],
    answer: 1,
    explanation: 'Tollens’ reagent is a mild oxidising agent that oxidises aldehydes to carboxylates.'
  },
  {
    id: 7,
    type: 'single',
    section: 'Mathematics',
    marks: 4,
    negative: 1,
    prompt: 'If f(x) = x³ − 3x, the local minimum value of f is:',
    options: ['−2', '0', '2', '4'],
    answer: 0,
    explanation:
      "f′(x) = 3x² − 3 = 0 at x = ±1. f″(1) > 0, so x = 1 is a local minimum and f(1) = −2."
  },
  {
    id: 8,
    type: 'single',
    section: 'Mathematics',
    marks: 4,
    negative: 1,
    prompt: 'The value of ∫₀¹ x·eˣ dx is:',
    options: ['1', 'e − 1', 'e', 'e + 1'],
    answer: 0,
    explanation: 'Integrating by parts gives [x·eˣ − eˣ]₀¹ = (e − e) − (0 − 1) = 1.'
  },
  {
    id: 9,
    type: 'single',
    section: 'Mathematics',
    marks: 4,
    negative: 1,
    prompt: 'The number of distinct real roots of x² − 4x + 4 = 0 is:',
    options: ['0', '1', '2', 'Infinite'],
    answer: 1,
    explanation: 'The discriminant is 16 − 16 = 0, so there is exactly one distinct real root (x = 2).'
  },
  {
    id: 10,
    type: 'single',
    section: 'Mathematics',
    marks: 4,
    negative: 1,
    prompt: 'If a vector has magnitude 5 and direction cosines (0.6, 0.8, 0), its components are:',
    options: ['(3, 4, 0)', '(4, 3, 0)', '(0, 3, 4)', '(5, 0, 0)'],
    answer: 0,
    explanation: 'Each component is the magnitude times the corresponding direction cosine: (5×0.6, 5×0.8, 0) = (3, 4, 0).'
  }
];

export const DASHBOARD = {
  student: { name: 'Aarav Gupta', initials: 'AG', streak: 12, level: 'Proficient' },
  stats: { courses: 3, lessonsDone: 148, testsTaken: 26, notes: 41 },
  continue: [
    { courseSlug: 'jee-main-2027-complete', glyph: 'JEE', title: 'Kinematics — Relative Motion', chapter: 'Physics · Mechanics', percent: 64, nextAt: '2h 14m' },
    { courseSlug: 'neet-2027-biology-intensive', glyph: 'NEET', title: 'Cell Cycle & Cell Division', chapter: 'Biology · Cell Biology', percent: 82, nextAt: '38m' },
    { courseSlug: 'ssc-cgl-2026-foundation', glyph: 'SSC', title: 'Percentage — Part 3', chapter: 'Quant · Arithmetic', percent: 31, nextAt: '1h 05m' }
  ],
  upcoming: [
    { day: '26', month: 'Oct', title: 'JEE Main Full Mock #12', meta: '2:00 PM · 90 questions' },
    { day: '28', month: 'Oct', title: 'SSC CGL Tier 1 — PYQ 2024', meta: '9:00 AM · 100 questions' },
    { day: '01', month: 'Nov', title: 'UPSC Prelims GS Paper 1', meta: '9:30 AM · 120 minutes' }
  ],
  performance: [
    { label: 'Mock 7', value: 52 },
    { label: 'Mock 8', value: 61 },
    { label: 'Mock 9', value: 58 },
    { label: 'Mock 10', value: 72 },
    { label: 'Mock 11', value: 78 },
    { label: 'Mock 12', value: 84 }
  ],
  recentNotes: [
    { title: 'Rotational motion — key formulae', body: 'τ = Iα, L = Iω, and rolling without slipping: v = ωR. Watch the sign convention for clockwise torque.', at: '2 days ago' },
    { title: 'Named reactions to revise', body: 'Cannizzaro, Aldol, Perkin, Reimer–Tiemann. Revisit the conditions for each before the next chemistry test.', at: '4 days ago' }
  ]
};

export const TESTIMONIALS = [
  {
    quote:
      'The daily practice problems are what changed things for me. Two months in, my mock percentile moved from 61 to 88.',
    name: 'Ishita Verma',
    meta: 'JEE Main aspirant · Jaipur',
    initials: 'IV',
    tone: 'violet'
  },
  {
    quote:
      'Being able to see exactly where I lost time per question made revision far less random. I stopped guessing what to study.',
    name: 'Rohan Patil',
    meta: 'SSC CGL aspirant · Pune',
    initials: 'RP',
    tone: 'amber'
  },
  {
    quote:
      'Notes and bookmarks sync across devices, so I can revise on the bus without opening five different apps.',
    name: 'Fatima Sheikh',
    meta: 'NEET aspirant · Hyderabad',
    initials: 'FS',
    tone: 'teal'
  }
];

export const FAQS = [
  {
    q: 'How do paid batches work?',
    a: 'Paid batches unlock with an access code issued by the institute. There is no checkout or card payment on this platform — you redeem a code and the batch is added to your account immediately.'
  },
  {
    q: 'Can I use the platform without downloading an app?',
    a: 'Yes. The site is installable as a progressive web app, so it works full-screen from your browser and keeps recently viewed lessons available when the connection drops.'
  },
  {
    q: 'Do tests have negative marking?',
    a: 'Each test carries its own marking scheme, shown before you start. Scores are calculated on the server, so a result cannot be altered by the browser.'
  },
  {
    q: 'Will I get an All-India rank?',
    a: 'Rank and percentile are produced for every scheduled mock once the window closes. Practice sets and chapter tests show a percentile band instead.'
  },
  {
    q: 'Is my data private?',
    a: 'Notes, bookmarks and progress are visible only to you. We do not run behavioural advertising or sell learner data.'
  }
];
