/**
 * Deterministic API stub for the offline DOM checks.
 *
 * The front end no longer ships fixtures, so the offline suites answer its
 * requests from here instead: the same shapes the Django serializers return,
 * with just enough rows to exercise a page. Nothing in this file reaches the
 * browser — it is a test double for jsdom only.
 *
 * `live.js` is the counterpart that uses the real server.
 */

/** Attempt timestamps are relative to the run, so a stub never looks expired. */
const iso = (offsetMs = 0) => new Date(Date.now() + offsetMs).toISOString();

const COURSES = [
  {
    id: 1,
    title: 'JEE Main 2027 Complete Batch',
    slug: 'jee-main-2027',
    description: 'Physics, Chemistry and Mathematics for the January session.',
    subject: 'Physics',
    exam: 'JEE Main',
    level: 'Class 12',
    pricing_mode: 'paid',
    price: '4499.00',
    has_access: false,
    telegram_handle: '@studyspace_access',
    telegram_dm:
      'https://t.me/studyspace_access?text=Hi%21+I+want+an+access+code+for+the+batch+%22JEE+Main+2027+Complete+Batch%22+%28batch+%231+%C2%B7+jee-main-2027%29.',
    lesson_count: 5,
    quiz_count: 2,
    folder_count: 2,
    timezone: 'Asia/Kolkata',
    is_published: true,
    created_at: '2026-09-01T10:00:00Z'
  },
  {
    id: 2,
    title: 'NEET Biology Foundation',
    slug: 'neet-biology-foundation',
    description: 'Class 11 biology, chapter by chapter.',
    subject: 'Biology',
    exam: 'NEET',
    level: 'Class 12',
    pricing_mode: 'free',
    price: '0.00',
    has_access: true,
    lesson_count: 3,
    quiz_count: 1,
    folder_count: 1,
    timezone: 'Asia/Kolkata',
    is_published: true,
    created_at: '2026-09-02T10:00:00Z'
  },
  {
    id: 3,
    title: 'SSC CGL Quantitative Aptitude',
    slug: 'ssc-cgl-quant',
    description: 'Arithmetic and advanced maths for tier 1 and tier 2.',
    subject: 'Quantitative Aptitude',
    exam: 'SSC CGL',
    level: 'Graduate',
    pricing_mode: 'free',
    price: '0.00',
    has_access: true,
    lesson_count: 2,
    quiz_count: 1,
    folder_count: 1,
    timezone: 'Asia/Kolkata',
    is_published: true,
    created_at: '2026-09-03T10:00:00Z'
  }
];

const LESSONS = [
  { id: 11, course: 1, folder: 101, title: 'Units and measurement', description: '', video_url: 'https://embed.vcdn.me/embed/28c4af9f-d817-460a-80ab-9a09f8c47c69', starts_at: iso(-4 * 3600000), duration_minutes: 42, position: 1, is_published: true, is_locked: false },
  { id: 12, course: 1, folder: 101, title: 'Kinematics in one dimension', description: 'Displacement, velocity and acceleration.', video_url: 'https://cdn.example/kinematics.mp4', duration_minutes: 51, position: 2, is_published: true, is_locked: false },
  { id: 13, course: 1, folder: 102, title: 'Mole concept', description: '', video_url: '', duration_minutes: 38, position: 1, is_published: true, is_locked: false },
  { id: 21, course: 2, folder: 201, title: 'Cell — the unit of life', description: '', video_url: '', duration_minutes: 44, position: 1, is_published: true, is_locked: false }
];

const QUESTIONS = [1, 2, 3].map((n) => ({
  id: n,
  prompt: `Stub question ${n}: pick the correct option.`,
  position: n,
  choices: [
    { id: n * 10 + 1, text: 'First option' },
    { id: n * 10 + 2, text: 'Second option' },
    { id: n * 10 + 3, text: 'Third option' },
    { id: n * 10 + 4, text: 'Fourth option' }
  ],
  question_type: 'single_choice',
  marks: null,
  negative_marks: null,
  difficulty: 'medium',
  // A paper question carries two labels: the section it sits in (the exam
  // window's tabs) and the chapter it tests (the result analysis).
  section: 'Physics',
  topic: 'Kinematics'
}));

const QUIZZES = [
  {
    id: 5,
    course: null,
    series: 1,
    title: 'JEE Main Full Mock #12',
    description: '3 questions · 30 minutes',
    instructions: 'The paper is timed and scored on the server.',
    timing_mode: 'timed',
    duration_minutes: 30,
    attempt_limit: null,
    marks_per_question: '4.00',
    negative_marks_per_wrong: '1.00',
    opens_at: '2026-10-20T09:00:00+05:30',
    closes_at: null,
    is_published: true,
    has_access: true,
    question_count: 3,
    questions: QUESTIONS,
    series_title: 'JEE Main Mocks',
    series_subject: 'Physics',
    course_title: null,
    course_slug: null,
    course_subject: null,
    attempt_count: 120,
    created_at: '2026-09-10T10:00:00Z',
    updated_at: '2026-09-10T10:00:00Z'
  },
  {
    id: 6,
    course: 1,
    series: null,
    title: 'Kinematics sectional',
    description: '3 questions · 30 minutes',
    instructions: '',
    timing_mode: 'timed',
    duration_minutes: 30,
    attempt_limit: null,
    marks_per_question: '4.00',
    negative_marks_per_wrong: '1.00',
    opens_at: null,
    closes_at: null,
    is_published: true,
    has_access: false,
    question_count: 3,
    questions: [],
    series_title: null,
    series_subject: null,
    course_title: 'JEE Main 2027 Complete Batch',
    course_slug: 'jee-main-2027',
    course_subject: 'Physics',
    attempt_count: 12,
    created_at: '2026-09-11T10:00:00Z',
    updated_at: '2026-09-11T10:00:00Z'
  }
];

const PDFS = [
  { id: 1, folder: 101, title: 'Units and measurement — notes', description: 'PDF notes', file_url: 'https://files.example/units.pdf', position: 1, is_protected: false, is_locked: false },
  { id: 2, folder: 102, title: 'Mole concept — notes', description: 'PDF notes', file_url: null, position: 1, is_protected: true, is_locked: true }
];

const COMMUNITY = [
  {
    id: 1,
    title: 'Doubts session moved to Friday',
    body: 'The Saturday doubt session moves to Friday 7 pm.',
    author: 1,
    author_name: 'Rehan Sir',
    course: 1,
    course_title: 'JEE Main 2027 Complete Batch',
    course_slug: 'jee-main-2027',
    pinned: true,
    created_at: '2026-10-25T12:00:00Z'
  },
  {
    id: 2,
    title: 'New notes uploaded',
    body: 'Mole concept notes are on the batch page.',
    author: 1,
    author_name: 'Rehan Sir',
    course: 1,
    course_title: 'JEE Main 2027 Complete Batch',
    course_slug: 'jee-main-2027',
    pinned: false,
    created_at: '2026-10-24T12:00:00Z'
  }
];

const ATTEMPTS = [
  { id: 1, quiz: 5, status: 'submitted', started_at: '2026-10-24T09:00:00Z', deadline: '2026-10-24T09:30:00Z', submitted_at: '2026-10-24T09:28:00Z', score: '8.00', max_score: '12.00', question_order: [1, 2, 3], rules_snapshot: {}, result_released_at: '2026-10-24T09:28:00Z' }
];

const page = (rows) => ({ count: rows.length, next: null, previous: null, results: rows });

const RESULT = {
  id: 1,
  quiz: 5,
  status: 'submitted',
  started_at: '2026-10-27T09:00:00Z',
  deadline: '2026-10-27T09:30:00Z',
  submitted_at: '2026-10-27T09:10:00Z',
  score: '8.00',
  max_score: '12.00',
  percentage: 66.67,
  passed: null,
  time_taken_seconds: 600,
  correct_count: 2,
  incorrect_count: 0,
  unanswered_count: 1,
  marked_for_review_count: 0,
  answers_detail: QUESTIONS.map((question, index) => ({
    id: index + 1,
    question: question.id,
    selected_choices: index === 2 ? [] : [{ id: question.choices[0].id, text: question.choices[0].text }],
    correct_choices: [{ id: question.choices[0].id, text: question.choices[0].text }],
    answered: index !== 2,
    marked_for_review: false,
    is_correct: index !== 2,
    explanation: 'Worked explanation from the paper.',
    section: 'Physics',
    topic: index === 1 ? 'Thermodynamics' : 'Kinematics'
  })),
  topic_breakdown: [
    { topic: 'Kinematics', correct: 2, incorrect: 0, unanswered: 0, answered: 2, accuracy: 100, score: '8.00', max_score: '8.00' },
    { topic: 'Thermodynamics', correct: 0, incorrect: 0, unanswered: 1, answered: 0, accuracy: null, score: '0.00', max_score: '4.00' }
  ],
  result_released_at: '2026-10-27T09:10:00Z'
};

/* Weak-topic analysis. The rules travel with the payload so the screen prints
 * the threshold it actually used. */
/* The timetable. Times are relative to the run so a fixture never looks stale;
 * statuses are fixed here because the server computes them, not the page. */
const classEntry = (id, title, section, offsets, status, over = {}) => ({
  id,
  title,
  section,
  starts_at: iso(offsets[0]),
  ends_at: iso(offsets[1]),
  duration_minutes: Math.round((offsets[1] - offsets[0]) / 60000),
  status,
  recording: status !== 'upcoming',
  is_locked: false,
  can_open: true,
  course: { id: 1, title: 'JEE Main 2027 Complete Batch', slug: 'jee-main-2027' },
  ...over
});

const SCHEDULE_CLASSES = [
  classEntry(11, 'Kinematics in one dimension', 'Mechanics', [-12 * 60000, 40 * 60000], 'live'),
  classEntry(12, 'Units, dimensions and errors', 'Mechanics', [-4 * 3600000, -3 * 3600000], 'ended'),
  classEntry(14, 'Mole concept', 'Chemistry', [2 * 3600000, 3 * 3600000], 'upcoming', { recording: false }),
  classEntry(21, 'Cell — the unit of life', 'Cell Biology', [20 * 3600000, 21 * 3600000], 'upcoming', {
    recording: false,
    course: { id: 2, title: 'NEET Biology Foundation', slug: 'neet-biology-foundation' }
  })
];

/** Groups the classes by local day, the way `courses/schedule.py` does. */
function schedulePayload({ course = null, quiet = false, empty = false } = {}) {
  let pool = quiet ? SCHEDULE_CLASSES.slice(3) : SCHEDULE_CLASSES.slice();
  if (course) pool = pool.filter((entry) => entry.course.slug === course);
  if (empty) pool = [];

  const groups = [];
  for (const entry of pool) {
    const day = new Date(entry.starts_at).toLocaleDateString('en-CA');
    let group = groups.find((row) => row.date === day);
    if (!group) {
      const date = new Date(entry.starts_at);
      group = {
        date: day,
        label: date.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' }),
        is_today: new Date(entry.starts_at).toDateString() === new Date().toDateString(),
        classes: []
      };
      groups.push(group);
    }
    group.classes.push(entry);
  }
  groups.sort((a, b) => a.date.localeCompare(b.date));

  const all = groups.flatMap((group) => group.classes);
  const today = groups.find((group) => group.is_today);
  return {
    timezone: 'Asia/Kolkata',
    now: iso(0),
    scope: course ? 'course' : 'mine',
    window_days: 7,
    counts: {
      today: today ? today.classes.length : 0,
      live: all.filter((entry) => entry.status === 'live').length,
      upcoming: all.filter((entry) => entry.status === 'upcoming').length,
      total: all.length
    },
    groups,
    next: all.find((entry) => entry.status === 'live') || all.find((entry) => entry.status === 'upcoming') || null,
    ...(course ? { course: pool[0]?.course || null } : {})
  };
}

const INSIGHTS = {
  released_attempts: 2,
  questions: 9,
  topics: [
    { topic: 'Kinematics', questions: 5, correct: 1, incorrect: 4, unanswered: 0, answered: 5, accuracy: 20, score: '4.00', max_score: '20.00', attempts: 2 },
    { topic: 'Thermodynamics', questions: 3, correct: 2, incorrect: 1, unanswered: 0, answered: 3, accuracy: 66.7, score: '8.00', max_score: '12.00', attempts: 1 },
    { topic: 'Thermodynamics (blank chapter)', questions: 1, correct: 0, incorrect: 0, unanswered: 1, answered: 0, accuracy: null, score: '0.00', max_score: '4.00', attempts: 1 }
  ],
  focus: [
    { topic: 'Kinematics', questions: 5, correct: 1, incorrect: 4, unanswered: 0, answered: 5, accuracy: 20, score: '4.00', max_score: '20.00', attempts: 2 }
  ],
  rules: { min_answered: 3, weak_below: 60 }
};

const json = (body, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' }
    })
  );

/**
 * @param {object} opts
 *   signedIn  — answer /auth/me/ and the personal endpoints
 *   empty     — serve an empty catalogue (the "nothing published" path)
 *   noTelegram — every batch is served without a Telegram handle, so the
 *               "Get code" button has nothing to point at
 *   emptyInsights — a learner with no released papers (the empty focus panel)
 *   quietSchedule — nothing today, one class later in the week
 *   emptySchedule — nothing scheduled at all in the window
 */
/* A paper frozen at attempt start. The prompts deliberately differ from the
 * live `QUESTIONS`, so a test can prove the player renders the attempt's copy
 * and not today's question bank. */
const FROZEN_PAPER = {
  quiz: { marks_per_question: '2.00', negative_marks_per_wrong: '0.50' },
  questions: [
    {
      id: 1,
      position: 0,
      prompt: 'FROZEN: the paper that was served',
      question_type: 'single_choice',
      section: 'Frozen section',
      topic: 'Frozen chapter',
      marks: '2.00',
      negative_marks: '0.50',
      choices: [
        { id: 11, text: 'Frozen option A', position: 1 },
        { id: 12, text: 'Frozen option B', position: 2 }
      ]
    }
  ]
};

function makeStub({
  signedIn = false,
  empty = false,
  noTelegram = false,
  frozenPaper = false,
  mcq = false,
  emptyInsights = false,
  quietSchedule = false,
  emptySchedule = false
} = {}) {
  const pick = (rows) =>
    (empty ? [] : noTelegram ? rows.map((row) => ({ ...row, telegram_dm: '', telegram_handle: '' })) : rows);

  // `mcq` turns the first question into a multiple-choice one, so a test can
  // select two options and prove the payload carries both.
  const paperQuestions = mcq
    ? QUESTIONS.map((question, index) =>
        index === 0 ? { ...question, question_type: 'multiple_choice' } : question
      )
    : QUESTIONS;
  const quizRows = () =>
    QUIZZES.map((row) => (row.id === 5 ? { ...row, questions: paperQuestions } : row));
  // Read receipts are the one piece of inbox state the real server persists,
  // so the stub keeps them too; otherwise "mark all read" could never clear.
  const readKeys = new Set();

  /** The catalogue with the request's filters applied; `skip` omits one facet. */
  function filterCourses(params, skip = null) {
    let rows = pick(COURSES).filter((course) => course.is_published !== false);
    const slug = params.get('slug');
    if (slug) rows = rows.filter((course) => course.slug === slug);
    if (params.get('mine') === '1') rows = rows.filter((course) => course.has_access);
    const search = (params.get('search') || '').toLowerCase();
    if (search) {
      rows = rows.filter((course) =>
        `${course.title} ${course.description || ''} ${course.subject} ${course.exam || ''} ${course.level || ''}`
          .toLowerCase()
          .includes(search)
      );
    }
    for (const field of ['exam', 'subject', 'level']) {
      if (field === skip) continue;
      const values = params.getAll(field).map((value) => value.toLowerCase());
      if (values.length) {
        rows = rows.filter((course) => values.includes(String(course[field] || '').toLowerCase()));
      }
    }
    if (skip !== 'pricing_mode') {
      const pricing = params.get('pricing_mode');
      if (pricing) rows = rows.filter((course) => course.pricing_mode === pricing);
    }
    return rows;
  }

  return (rawUrl, init = {}) => {
    const url = new URL(rawUrl, 'https://stub.local');
    const path = url.pathname.replace(/^\/api/, '');
    const method = (init.method || 'GET').toUpperCase();
    const headers = init.headers || {};
    const authed = signedIn || Boolean(headers.Authorization);
    const guest = Boolean(headers['X-Attempt-Token']);

    if (path === '/courses/' || path === '/courses') {
      return json(page(filterCourses(url.searchParams)));
    }

    // Counts the way the real viewset counts: each group is computed with the
    // others applied and its own left out, so ticking one value never hides
    // its siblings.
    if (path === '/courses/facets/' || path === '/courses/facets') {
      const groups = {};
      for (const field of ['exam', 'subject', 'level']) {
        const counts = new Map();
        for (const course of filterCourses(url.searchParams, field)) {
          if (course[field]) counts.set(course[field], (counts.get(course[field]) || 0) + 1);
        }
        groups[field] = [...counts.entries()]
          .map(([value, count]) => ({ value, count }))
          .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
      }
      const priced = filterCourses(url.searchParams, 'pricing_mode');
      groups.pricing_mode = ['free', 'paid']
        .map((value) => ({ value, count: priced.filter((course) => course.pricing_mode === value).length }))
        .filter((row) => row.count > 0);
      return json({ count: filterCourses(url.searchParams).length, facets: groups });
    }

    const courseDetail = path.match(/^\/courses\/(\d+)\/$/);
    if (courseDetail) {
      // `pick` so `--empty` / `noTelegram` reach the detail endpoint too.
      const course = pick(COURSES).find((row) => row.id === Number(courseDetail[1]));
      if (!course) return json({ detail: 'Not found.' }, 404);
      return json({
        ...course,
        faculty: [
          { id: 1, name: 'Dr. Meera Kulkarni', subject: 'Physics', bio: 'Writes the weekly problem sets.', avatar_url: '', position: 1 },
          { id: 2, name: 'Anil Bhatt', subject: 'Mathematics', bio: '', avatar_url: '', position: 2 }
        ],
        folders: [
          {
            id: 101,
            title: 'Mechanics',
            description: 'Motion, forces and energy.',
            position: 1,
            lessons: LESSONS.filter((lesson) => lesson.folder === 101),
            pdf_resources: PDFS.filter((pdf) => pdf.folder === 101)
          },
          {
            id: 102,
            title: 'Physical chemistry',
            description: '',
            position: 2,
            lessons: LESSONS.filter((lesson) => lesson.folder === 102),
            pdf_resources: PDFS.filter((pdf) => pdf.folder === 102)
          }
        ]
      });
    }

    if (path === '/lessons/' || path === '/lessons') {
      let rows = pick(LESSONS);
      const course = url.searchParams.get('course');
      if (course) rows = rows.filter((lesson) => lesson.course === Number(course));
      return json(page(rows));
    }

    const lessonDetail = path.match(/^\/lessons\/(\d+)\/$/);
    if (lessonDetail) {
      const lesson = LESSONS.find((row) => row.id === Number(lessonDetail[1]));
      if (!lesson) return json({ detail: 'Not found.' }, 404);
      const course = COURSES.find((row) => row.id === lesson.course);
      return json({ ...lesson, course_title: course?.title, folder_title: 'Mechanics' });
    }

    if (path === '/quizzes/' || path === '/quizzes') {
      let rows = pick(QUIZZES);
      const course = url.searchParams.get('course');
      if (course) rows = rows.filter((quiz) => String(quiz.course) === String(course));
      // A list response never carries the question payload for a locked paper.
      return json(page(rows.map((quiz) => (quiz.has_access ? quiz : { ...quiz, questions: [] }))));
    }

    const quizDetail = path.match(/^\/quizzes\/(\d+)\/$/);
    if (quizDetail) {
      const quiz = quizRows().find((row) => row.id === Number(quizDetail[1]));
      if (!quiz) return json({ detail: 'Not found.' }, 404);
      return json(quiz);
    }

    if (path === '/quizzes/start/') {
      if (!authed && !guest && empty) return json({ detail: 'Not available.' }, 403);
      return json(
        {
          id: 1,
          quiz: 5,
          status: 'in_progress',
          started_at: iso(),
          deadline: iso(30 * 60 * 1000),
          question_order: [1, 2, 3],
          rules_snapshot: { duration_minutes: 30, marks_per_question: '4.00' },
          ...(frozenPaper ? { paper: FROZEN_PAPER } : {}),
          ...(authed ? {} : { guest_token: 'stub-guest-token' })
        },
        201
      );
    }

    if (/^\/quiz-attempts\/\d+\/(autosave|submit)\/$/.test(path) && method === 'POST') {
      return json(/submit/.test(path) ? RESULT : { status: 'saved' });
    }
    if (/^\/quiz-attempts\/\d+\/result\/$/.test(path)) return json(RESULT);
    if (/^\/quiz-attempts\/\d+\/$/.test(path)) {
      return json({
        id: 1,
        quiz: 5,
        status: 'in_progress',
        started_at: iso(),
        deadline: iso(30 * 60 * 1000),
        question_order: [1, 2, 3],
        rules_snapshot: { duration_minutes: 30 }
      });
    }

    if (path === '/community/' || path === '/community') {
      let rows = pick(COMMUNITY);
      const course = url.searchParams.get('course');
      if (course) rows = rows.filter((post) => String(post.course) === String(course));
      return json(page(rows));
    }

    if (path === '/pdfs/' || path === '/pdfs') {
      let rows = pick(PDFS);
      const course = url.searchParams.get('course');
      if (course) rows = rows.filter(() => Number(course) === 1 || empty);
      return json(page(rows));
    }

    if (path === '/notes/' && method === 'POST') {
      if (!authed) return json({ detail: 'Authentication credentials were not provided.' }, 401);
      const body = JSON.parse(init.body || '{}');
      return json(
        {
          id: 77,
          lesson: body.lesson ?? null,
          lesson_title: body.lesson ? 'Units and measurement' : null,
          title: body.title || 'Class note',
          body: body.body || '',
          updated_at: iso()
        },
        201
      );
    }

    if (path === '/notes/') {
      if (!authed && !signedIn) return json({ detail: 'Authentication credentials were not provided.' }, 401);
      const lesson = url.searchParams.get('lesson');
      const rows = [
        { id: 1, lesson: 11, lesson_title: 'Units and measurement', title: 'Rotational motion', body: 'τ = Iα', updated_at: '2026-10-26T10:00:00Z' }
      ];
      return json(page(lesson ? rows.filter((row) => String(row.lesson) === String(lesson)) : rows));
    }

    const noteDetail = path.match(/^\/notes\/(\d+)\/$/);
    if (noteDetail && method === 'DELETE') {
      return Promise.resolve(new Response(null, { status: 204 }));
    }

    if (path === '/progress/' && method === 'POST') {
      if (!authed) return json({ detail: 'Authentication credentials were not provided.' }, 401);
      const body = JSON.parse(init.body || '{}');
      return json(
        {
          id: 5,
          lesson: body.lesson,
          lesson_title: 'Units and measurement',
          completed: Boolean(body.completed),
          completed_at: body.completed ? iso() : null,
          updated_at: iso()
        },
        201
      );
    }

    if (path === '/progress/' && method === 'GET') {
      if (!authed && !signedIn) return json({ detail: 'Authentication credentials were not provided.' }, 401);
      const lesson = url.searchParams.get('lesson');
      // Two rows: one finished lesson (it feeds the streak and the week total)
      // and one merely opened (it is what "continue" should offer next).
      const finishedAt = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
      const rows = [
        { id: 2, lesson: 21, lesson_title: 'Cell — the unit of life', course: 2, lesson_duration_minutes: 45, completed: true, completed_at: finishedAt, updated_at: finishedAt },
        { id: 1, lesson: 21, lesson_title: 'Cell — the unit of life', course: 2, lesson_duration_minutes: 40, completed: false, completed_at: null, updated_at: '2026-10-26T10:00:00Z' }
      ];
      let out = rows;
      if (lesson) out = out.filter((row) => String(row.lesson) === String(lesson));
      const only = url.searchParams.get('completed');
      if (only === '1') out = out.filter((row) => row.completed);
      if (only === '0') out = out.filter((row) => !row.completed);
      return json(page(out));
    }

    if (path === '/study-tasks/' && method === 'POST') {
      if (!authed) return json({ detail: 'Authentication credentials were not provided.' }, 401);
      const body = JSON.parse(init.body || '{}');
      return json({ id: 9, title: body.title, due_at: body.due_at || null, is_completed: false }, 201);
    }

    if (/^\/study-tasks\/\d+\/(complete|reopen)\/$/.test(path) && method === 'POST') {
      const done = /complete/.test(path);
      return json({ id: 1, title: 'Revise mole concept', due_at: '2026-10-28T10:00:00Z', is_completed: done });
    }

    if (path === '/schedule/' || path === '/schedule') {
      const course = url.searchParams.get('course');
      if (!course && !(signedIn || authed)) {
        return json({ detail: 'Sign in to see your timetable.' }, 401);
      }
      return json(schedulePayload({ course, quiet: quietSchedule, empty: emptySchedule }));
    }
    if (path === '/insights/topics/') {
      return signedIn || authed
        ? json(emptyInsights ? { ...INSIGHTS, topics: [], focus: [], released_attempts: 0, questions: 0 } : INSIGHTS)
        : json({ detail: 'Authentication credentials were not provided.' }, 401);
    }
    if (path === '/notifications/') {
      const items = [
        { id: 'announcement:1', kind: 'announcement', title: 'Mock test schedule', body: 'Two papers are open this week.', href: 'community.html', at: iso() },
        { id: 'task:1', kind: 'task', title: 'Revise mole concept', body: 'Due today', href: 'dashboard.html#task-list', at: iso() }
      ].map((item) => ({ ...item, read: readKeys.has(item.id) }));
      return json({
        count: items.length,
        unread: items.filter((item) => !item.read).length,
        results: items
      });
    }

    if (path === '/notifications/read/' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      (body.keys || []).forEach((key) => readKeys.add(key));
      return json({ marked: (body.keys || []).length, unread: 0 });
    }

    if (path === '/question-reports/' && method === 'POST') {
      const body = JSON.parse(init.body || '{}');
      return json(
        { id: 1, attempt: body.attempt, question: body.question, reason: body.reason, detail: body.detail || '', status: 'open', created_at: iso() },
        201
      );
    }
    if (path === '/study-tasks/') return authed || signedIn ? json(page([{ id: 1, title: 'Revise mole concept', due_at: '2026-10-28T10:00:00Z', is_completed: false }])) : json({ detail: 'Authentication credentials were not provided.' }, 401);
    if (path === '/quiz-attempts/' || path === '/quiz-attempts') return authed || signedIn ? json(page(ATTEMPTS)) : json(page([]));
    if (path === '/auth/me/') return authed || signedIn ? json({ id: 1, username: 'stub_student', email: 'student@example.test', role: 'student', date_joined: '2026-09-01T10:00:00Z' }) : json({ detail: 'Authentication credentials were not provided.' }, 401);

    return json({ detail: `No stub for ${method} ${path}` }, 404);
  };
}

module.exports = { makeStub, COURSES, LESSONS, QUIZZES, COMMUNITY, PDFS, ATTEMPTS, RESULT, iso };
