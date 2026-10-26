/**
 * StudyMate AI - Frontend Application Controller
 * Handles interactive view navigation, AI completions, quiz generation,
 * document ingestion, semantic search queries, and accessible UI feedback.
 */

(() => {
  'use strict';

  // Quick DOM element selector
  const $ = (id) => document.getElementById(id);

  // Application State
  let currentMode = 'summarize';
  let activeQuizQuestions = [];

  // Helper: display errors in the error card
  function showError(message) {
    const errorCard = $('errorCard');
    const errorText = $('errorText');
    if (errorText && errorCard) {
      errorText.textContent = message;
      errorCard.hidden = false;
    }
  }

  // Helper: clear any active error display
  function clearError() {
    const errorCard = $('errorCard');
    if (errorCard) {
      errorCard.hidden = true;
    }
  }

  // Helper: button loading state toggle
  function setButtonLoading(button, isLoading, loadingText = 'Processing...') {
    if (!button) return;
    const textSpan = button.querySelector('.btn-text') || button;
    if (isLoading) {
      button.disabled = true;
      button.dataset.originalText = textSpan.textContent;
      textSpan.innerHTML = `<span class="spinner" aria-hidden="true"></span> ${loadingText}`;
    } else {
      button.disabled = false;
      if (button.dataset.originalText) {
        textSpan.textContent = button.dataset.originalText;
      }
    }
  }

  // Helper: parse basic markdown (headings, bold, bullets) into safe HTML
  function renderMarkdown(rawText) {
    if (!rawText) return '';

    // Escape HTML to prevent injection
    const escaped = rawText
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    const lines = escaped.split('\n');
    let html = '';
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (!line) {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        continue;
      }

      // H2 Headings
      if (line.startsWith('## ')) {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        html += `<h2>${line.substring(3).trim()}</h2>`;
      }
      // H3 Headings
      else if (line.startsWith('### ')) {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        html += `<h3>${line.substring(4).trim()}</h3>`;
      }
      // Bullet lists
      else if (line.startsWith('- ') || line.startsWith('* ')) {
        if (!inList) {
          html += '<ul style="margin: 8px 0; padding-left: 20px;">';
          inList = true;
        }
        let itemText = line.substring(2);
        // Inline bold
        itemText = itemText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html += `<li style="margin-bottom: 4px;">${itemText}</li>`;
      }
      // Standard paragraphs
      else {
        if (inList) {
          html += '</ul>';
          inList = false;
        }
        let paraText = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html += `<p style="margin: 8px 0;">${paraText}</p>`;
      }
    }

    if (inList) {
      html += '</ul>';
    }

    return html;
  }

  // Generic JSON Fetch Helper
  async function apiRequest(url, options = {}) {
    clearError();
    const response = await fetch(url, options).catch(() => null);

    if (!response) {
      throw new Error('Unable to connect to the server. Please verify your connection.');
    }

    const data = await response.json().catch(() => null);

    if (!response.ok || !data?.success) {
      const message = data?.error || `Request failed with status code ${response.status}.`;
      throw new Error(message);
    }

    return data;
  }

  // --- Mode Navigation ---
  $('modeGrid').addEventListener('click', (event) => {
    const card = event.target.closest('.mode-card');
    if (!card) return;

    currentMode = card.dataset.mode;
    $('wsIcon').textContent = card.dataset.icon;
    $('wsTitle').textContent = card.dataset.title;
    $('wsDesc').textContent = card.dataset.desc;

    // Toggle module-specific panels
    $('standardPanel').hidden = currentMode === 'quiz' || currentMode === 'rag';
    $('quizPanel').hidden = currentMode !== 'quiz';
    $('ragPanel').hidden = currentMode !== 'rag';

    // Reset results & errors
    $('resultCard').hidden = true;
    $('quizCard').hidden = true;
    $('ragResultCard').hidden = true;
    clearError();

    // Transition view
    $('hero').hidden = true;
    $('workspace').hidden = false;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  $('backBtn').addEventListener('click', () => {
    $('workspace').hidden = true;
    $('hero').hidden = false;
    clearError();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // --- Character Counters ---
  $('contentInput').addEventListener('input', (e) => {
    $('charCount').textContent = `${e.target.value.length} / 6000`;
  });

  $('clearBtn').addEventListener('click', () => {
    $('contentInput').value = '';
    $('charCount').textContent = '0 / 6000';
    $('resultCard').hidden = true;
    clearError();
  });

  // --- Standard AI Completions (Summarize, Explain, Improve) ---
  $('generateBtn').addEventListener('click', async () => {
    const content = $('contentInput').value.trim();

    if (content.length < 10) {
      return showError('Please provide a little more study content (at least 10 characters).');
    }

    const generateBtn = $('generateBtn');
    setButtonLoading(generateBtn, true, 'Thinking...');

    try {
      const data = await apiRequest('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: currentMode, content }),
      });

      const resultContent = $('resultContent');
      resultContent.innerHTML = renderMarkdown(data.response);
      $('resultCard').hidden = false;
      $('resultCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (err) {
      showError(err.message);
    } finally {
      setButtonLoading(generateBtn, false);
    }
  });

  // Copy AI response to clipboard with user feedback
  $('copyBtn').addEventListener('click', async () => {
    const text = $('resultContent').innerText;
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      const copyBtn = $('copyBtn');
      const originalText = copyBtn.textContent;
      copyBtn.textContent = '✓ Copied!';
      setTimeout(() => {
        copyBtn.textContent = originalText;
      }, 2000);
    } catch {
      showError('Failed to copy to clipboard.');
    }
  });

  // --- Quiz Generator ---
  $('quizBtn').addEventListener('click', async () => {
    const content = $('quizContent').value.trim();

    if (content.length < 10) {
      return showError('Please paste your study notes first to generate quiz questions.');
    }

    const numQuestions = parseInt($('quizCount').value, 10);
    const difficulty = $('quizDifficulty').value;
    const quizBtn = $('quizBtn');

    setButtonLoading(quizBtn, true, 'Generating Quiz...');

    try {
      const data = await apiRequest('/api/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          num_questions: numQuestions,
          difficulty,
        }),
      });

      activeQuizQuestions = data.quiz.questions;
      renderQuiz(activeQuizQuestions);
    } catch (err) {
      showError(err.message);
    } finally {
      setButtonLoading(quizBtn, false);
    }
  });

  $('newQuizBtn').addEventListener('click', () => {
    $('quizContent').value = '';
    $('quizCard').hidden = true;
    clearError();
  });

  $('generateNewQuizBtn').addEventListener('click', () => {
    $('quizBtn').click();
  });

  function renderQuiz(questions) {
    const form = $('quizForm');
    form.innerHTML = '';

    questions.forEach((q, qIndex) => {
      const fieldset = document.createElement('fieldset');
      fieldset.className = 'quiz-question';

      const legend = document.createElement('legend');
      legend.textContent = `${qIndex + 1}. ${q.question}`;
      fieldset.appendChild(legend);

      q.options.forEach((optText, optIndex) => {
        const label = document.createElement('label');
        label.className = 'quiz-option';

        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = `question_${qIndex}`;
        radio.value = optIndex;

        label.appendChild(radio);
        label.appendChild(document.createTextNode(` ${optText}`));
        fieldset.appendChild(label);
      });

      const feedback = document.createElement('div');
      feedback.id = `quizFeedback_${qIndex}`;
      feedback.className = 'quiz-feedback';
      fieldset.appendChild(feedback);

      form.appendChild(fieldset);
    });

    $('quizScore').hidden = true;
    $('submitQuizBtn').hidden = false;
    $('quizCard').hidden = false;
    $('quizCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  $('submitQuizBtn').addEventListener('click', () => {
    if (!activeQuizQuestions.length) return;

    let score = 0;
    let answeredCount = 0;

    activeQuizQuestions.forEach((q, i) => {
      const selected = document.querySelector(`input[name="question_${i}"]:checked`);
      const feedback = $(`quizFeedback_${i}`);

      if (selected) {
        answeredCount++;
        const isCorrect = parseInt(selected.value, 10) === q.correct_answer;
        if (isCorrect) score++;

        feedback.textContent = `${isCorrect ? '✓ Correct!' : '✗ Incorrect.'} Correct answer: "${q.options[q.correct_answer]}". ${q.explanation}`;
        feedback.className = `quiz-feedback ${isCorrect ? 'is-correct' : 'is-wrong'}`;
      } else {
        feedback.textContent = `Unanswered. Correct answer: "${q.options[q.correct_answer]}". ${q.explanation}`;
        feedback.className = 'quiz-feedback is-wrong';
      }
    });

    const scoreDiv = $('quizScore');
    const percentage = Math.round((score / activeQuizQuestions.length) * 100);
    scoreDiv.textContent = `Your Final Score: ${score} / ${activeQuizQuestions.length} (${percentage}%)`;
    scoreDiv.hidden = false;
    $('submitQuizBtn').hidden = true;
    scoreDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  // --- RAG Document Ingestion & Search ---
  $('uploadBtn').addEventListener('click', async () => {
    const fileInput = $('studyFile');
    const file = fileInput.files[0];

    if (!file) {
      return showError('Please select a PDF or TXT study file to upload.');
    }

    if (!/\.(pdf|txt)$/i.test(file.name)) {
      return showError('Unsupported file format. Please upload a PDF or TXT file.');
    }

    if (file.size > 10 * 1024 * 1024) {
      return showError('File is too large. Maximum supported file size is 10 MB.');
    }

    const uploadBtn = $('uploadBtn');
    setButtonLoading(uploadBtn, true, 'Indexing...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const data = await apiRequest('/api/rag/upload', {
        method: 'POST',
        body: formData,
      });

      const status = $('uploadStatus');
      status.textContent = `✓ "${data.filename}" is indexed successfully (${data.chunks} semantic sections ready).`;
    } catch (err) {
      showError(err.message);
    } finally {
      setButtonLoading(uploadBtn, false);
    }
  });

  $('askBtn').addEventListener('click', async () => {
    const question = $('ragQuestion').value.trim();

    if (!question) {
      return showError('Please enter a question to ask your notes.');
    }

    const askBtn = $('askBtn');
    setButtonLoading(askBtn, true, 'Searching Notes...');

    try {
      const data = await apiRequest('/api/rag/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      const ragAnswer = $('ragAnswer');
      ragAnswer.innerHTML = renderMarkdown(data.answer);

      const sourcesList = data.sources && data.sources.length
        ? data.sources.map((s) => `${s.filename} (Page ${s.page})`).join(', ')
        : 'Uploaded document';

      $('ragSources').textContent = `Document Sources: ${sourcesList}`;
      $('ragResultCard').hidden = false;
      $('ragResultCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (err) {
      showError(err.message);
    } finally {
      setButtonLoading(askBtn, false);
    }
  });

})();
