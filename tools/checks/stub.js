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
    pricing_mode: 'paid',
    price: '4499.00',
    has_access: false,
    lesson_count: 5,
    quiz_count: 2,
    folder_count: 2,
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
    pricing_mode: 'free',
    price: '0.00',
    has_access: true,
    lesson_count: 3,
    quiz_count: 1,
    folder_count: 1,
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
    pricing_mode: 'free',
    price: '0.00',
    has_access: true,
    lesson_count: 2,
    quiz_count: 1,
    folder_count: 1,
    is_published: true,
    created_at: '2026-09-03T10:00:00Z'
  }
];

const LESSONS = [
  { id: 11, course: 1, folder: 101, title: 'Units and measurement', description: '', video_url: '', duration_minutes: 42, position: 1, is_published: true, is_locked: false },
  { id: 12, course: 1, folder: 101, title: 'Kinematics in one dimension', description: 'Displacement, velocity and acceleration.', video_url: '', duration_minutes: 51, position: 2, is_published: true, is_locked: false },
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
  topic: 'Physics'
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
    explanation: 'Worked explanation from the paper.'
  })),
  section_breakdown: [
    { section: 'Physics', correct: 2, incorrect: 0, unanswered: 1, score: '8.00', max_score: '12.00' }
  ],
  result_released_at: '2026-10-27T09:10:00Z'
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
 */
function makeStub({ signedIn = false, empty = false } = {}) {
  const pick = (rows) => (empty ? [] : rows);

  return (rawUrl, init = {}) => {
    const url = new URL(rawUrl, 'https://stub.local');
    const path = url.pathname.replace(/^\/api/, '');
    const method = (init.method || 'GET').toUpperCase();
    const headers = init.headers || {};
    const authed = signedIn || Boolean(headers.Authorization);
    const guest = Boolean(headers['X-Attempt-Token']);

    if (path === '/courses/' || path === '/courses') {
      const slug = url.searchParams.get('slug');
      const mine = url.searchParams.get('mine');
      let rows = pick(COURSES);
      const pricing = url.searchParams.get('pricing_mode');
      const subject = url.searchParams.get('subject');
      const search = url.searchParams.get('search');
      if (slug) rows = rows.filter((course) => course.slug === slug);
      if (mine) rows = rows.filter((course) => course.has_access);
      if (pricing) rows = rows.filter((course) => course.pricing_mode === pricing);
      if (subject) rows = rows.filter((course) => course.subject === subject);
      if (search) {
        const needle = search.toLowerCase();
        rows = rows.filter((course) => `${course.title} ${course.subject}`.toLowerCase().includes(needle));
      }
      return json(page(rows));
    }

    const courseDetail = path.match(/^\/courses\/(\d+)\/$/);
    if (courseDetail) {
      const course = COURSES.find((row) => row.id === Number(courseDetail[1]));
      if (!course) return json({ detail: 'Not found.' }, 404);
      return json({
        ...course,
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
      const quiz = QUIZZES.find((row) => row.id === Number(quizDetail[1]));
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

    if (path === '/notes/') return authed || signedIn ? json(page([{ id: 1, title: 'Rotational motion', body: 'τ = Iα', updated_at: '2026-10-26T10:00:00Z' }])) : json({ detail: 'Authentication credentials were not provided.' }, 401);
    if (path === '/progress/') return authed || signedIn ? json(page([{ id: 1, lesson: 12, lesson_title: 'Kinematics in one dimension', completed: false, updated_at: '2026-10-26T10:00:00Z' }])) : json({ detail: 'Authentication credentials were not provided.' }, 401);
    if (path === '/study-tasks/') return authed || signedIn ? json(page([{ id: 1, title: 'Revise mole concept', due_at: '2026-10-28T10:00:00Z', is_completed: false }])) : json({ detail: 'Authentication credentials were not provided.' }, 401);
    if (path === '/quiz-attempts/' || path === '/quiz-attempts') return authed || signedIn ? json(page(ATTEMPTS)) : json(page([]));
    if (path === '/auth/me/') return authed || signedIn ? json({ id: 1, username: 'stub_student', email: 'student@example.test', role: 'student', date_joined: '2026-09-01T10:00:00Z' }) : json({ detail: 'Authentication credentials were not provided.' }, 401);

    return json({ detail: `No stub for ${method} ${path}` }, 404);
  };
}

module.exports = { makeStub, COURSES, LESSONS, QUIZZES, COMMUNITY, PDFS, ATTEMPTS, RESULT, iso };
