/**
 * StudySpace content — the copy that is genuinely editorial.
 *
 * Everything factual on this site (batches, lessons, tests, questions, notes,
 * announcements, results) is read from the Django API. What lives here is only
 * text we write ourselves: the FAQ, the profile menu and the "how it works"
 * steps. Nothing in this file may stand in for a database row.
 */

export const FAQS = [
  {
    q: 'How do paid batches work?',
    a: 'A paid batch unlocks with an access code issued by your institute. There is no checkout or card payment on this platform: you redeem the code on the batch page and the batch is added to your account immediately.'
  },
  {
    q: 'Do I need an account to attempt a test?',
    a: 'No. A free paper can be attempted straight away — the paper is still created, timed and scored on the server, and the result stays available on this device. Signing in adds the attempt to your history so it survives a cleared browser.'
  },
  {
    q: 'Do tests have negative marking?',
    a: 'Each test carries its own marking scheme, and it is shown before you start. Scores are calculated on the server from the stored answers, so a result cannot be altered by the browser.'
  },
  {
    q: 'What does my result show?',
    a: 'Your score and the maximum score for that paper, the marks earned against the marking scheme, and a question-by-question review of what you answered. Only what the server scored is shown.'
  },
  {
    q: 'Is my data private?',
    a: 'Notes, progress and attempts belong to your account and are visible only to you. A guest attempt is addressed by a token kept on this device, and the server stores only a hash of it. We do not run behavioural advertising or sell learner data.'
  },
  {
    q: 'Can I use the platform without installing an app?',
    a: 'Yes. The site installs as a progressive web app, so it opens full-screen from the browser and keeps the page shell available when the connection drops. Content itself always comes from the API.'
  }
];

export const PROFILE_MENU = [
  { label: 'My batches', href: 'courses.html?mine=1', icon: 'book' },
  { label: 'My attempts', href: 'tests.html#attempted', icon: 'file-text' },
  { label: 'Downloads', href: 'downloads.html', icon: 'download' },
  { label: 'Announcements', href: 'community.html', icon: 'message' },
  { label: 'Help & support', href: 'legal.html#codes', icon: 'info' }
];

export const HOW_IT_WORKS = [
  [
    'Start the paper',
    'The attempt is created on the server: question order, marking scheme and duration are frozen at that moment.'
  ],
  [
    'Answer with the exam palette',
    'Mark for review, clear a response and jump between questions. Every answer is autosaved to the server as you go.'
  ],
  [
    'Submit on the clock',
    'The timer is the server deadline, not a browser countdown. When it runs out the attempt closes and is scored automatically.'
  ],
  [
    'Read the review',
    'You get the score, the marking math and a question-by-question review of what you answered.'
  ]
];
