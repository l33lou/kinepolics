/* ==========================================================
   CinéClub Student Association - Client Application Logic
   KinepoliCS: Auth, Admin, Movie Suggestions, Popcorn, History & Stats
   ========================================================== */

// Configuration de l'URL API :
// - En local (localhost / 127.0.0.1) : utilise le serveur local ("")
// - En production sur Render ou hébergement externe : utilise l'URL Render
const API_BASE_URL = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" || window.location.hostname === "0.0.0.0")
  ? ""
  : "https://kinepolics.onrender.com";

(function () {
  'use strict';

  // Helper: Escape HTML to prevent XSS
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // State
  const state = {
    token: localStorage.getItem('cinema_token') || '',
    user: JSON.parse(localStorage.getItem('cinema_user') || 'null'),
    username: localStorage.getItem('cinema_username') || '',
    cart: JSON.parse(localStorage.getItem('cinema_cart') || '[]'),
    myOrders: JSON.parse(localStorage.getItem('cinema_my_orders') || '[]'),
    activeGenre: 'all',
    movies: [],
    products: [],
    screenings: [],
    selectedTmdbMovie: null,
    searchDebounceTimer: null,
    selectedReviewRating: 5,
    authMode: 'login', // 'login' or 'register'
    get isAdmin() {
      return !!(this.user && this.user.is_admin);
    }
  };

  // Helper: Fetch with API_BASE_URL and Authorization header if token exists
  async function authFetch(url, options = {}) {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    const headers = options.headers || {};
    if (state.token) {
      headers['Authorization'] = `Bearer ${state.token}`;
    }
    return fetch(fullUrl, { ...options, headers });
  }

  // DOM Elements
  const elements = {
    navLinks: document.querySelectorAll('.nav-link, .film-frame'),
    tabPanes: document.querySelectorAll('.tab-pane, .tab-content, section[id]'),

    // Auth
    loginBtn: document.getElementById('loginBtn'),
    logoutBtn: document.getElementById('logoutBtn'),
    userDisplayName: document.getElementById('user-display-name') || document.querySelector('#loginBtn span'),
    authModal: document.getElementById('auth-modal'),
    closeAuthModalBtn: document.getElementById('close-auth-modal-btn'),
    authForm: document.getElementById('auth-form'),
    authModalTitle: document.getElementById('auth-modal-title'),
    tabLoginBtn: document.getElementById('tab-login-btn'),
    tabRegisterBtn: document.getElementById('tab-register-btn'),
    authUsernameInput: document.getElementById('auth-username-input'),
    authPasswordInput: document.getElementById('auth-password-input'),
    submitAuthBtn: document.getElementById('submit-auth-btn'),
    authErrorBanner: document.getElementById('auth-error-banner'),

    // Suggestions / Movies
    moviesGrid: document.getElementById('movies-grid') || document.querySelector('.movie-grid'),
    genreFilters: document.getElementById('genre-filters'),

    // Snacks & Cart
    snacksGrid: document.getElementById('snacks-grid') || document.querySelector('.snack-grid'),
    openCartBtn: document.getElementById('open-cart-btn') || document.getElementById('cartBtn'),
    closeCartBtn: document.getElementById('close-cart-btn'),
    cartBackdrop: document.getElementById('cart-backdrop'),
    cartDrawer: document.getElementById('cart-drawer'),
    cartItemsList: document.getElementById('cart-items-list'),
    cartTotalDisplay: document.getElementById('cart-total-display'),
    headerCartCount: document.getElementById('cartCount') || document.getElementById('header-cart-count'),
    checkoutNameInput: document.getElementById('checkout-name-input'),
    placeOrderBtn: document.getElementById('place-order-btn'),
    cartBrowseBtn: document.getElementById('cart-browse-btn'),
    adminAddProductBtn: document.getElementById('admin-add-product-btn'),

    // Admin Product Modal
    adminProductModal: document.getElementById('admin-product-modal'),
    closeProductModalBtn: document.getElementById('close-product-modal-btn'),
    adminProductForm: document.getElementById('admin-product-form'),
    adminProductId: document.getElementById('admin-product-id'),
    adminProductName: document.getElementById('admin-product-name'),
    adminProductPrice: document.getElementById('admin-product-price'),
    adminProductCategory: document.getElementById('admin-product-category'),
    adminProductFlavor: document.getElementById('admin-product-flavor'),
    adminProductSize: document.getElementById('admin-product-size'),
    adminProductEmoji: document.getElementById('admin-product-emoji'),
    adminProductModalTitle: document.getElementById('admin-product-modal-title'),

    // Success Modal
    orderSuccessModal: document.getElementById('order-success-modal'),
    closeSuccessModalBtn: document.getElementById('close-success-modal-btn'),
    successOrderCode: document.getElementById('success-order-code'),
    successCustomerName: document.getElementById('success-customer-name'),
    successTotalPrice: document.getElementById('success-total-price'),
    successItemsList: document.getElementById('success-items-list'),

    // History Container & Review Modal
    historyList: document.getElementById('history-list'),
    reviewModal: document.getElementById('review-modal'),
    closeReviewModalBtn: document.getElementById('close-review-modal-btn'),
    reviewForm: document.getElementById('review-form'),
    reviewMovieId: document.getElementById('review-movie-id'),
    reviewMovieTitle: document.getElementById('review-movie-title'),
    starPicker: document.getElementById('star-picker'),
    starPickerLabel: document.getElementById('star-picker-label'),
    reviewRatingValue: document.getElementById('review-rating-value'),
    reviewTextInput: document.getElementById('review-text-input'),
    reviewWordInput: document.getElementById('review-word-input'),

    // Toast
    toastContainer: document.getElementById('toast-container'),

    // Suggestion Modal
    openSuggestModalBtn: document.getElementById('open-suggest-modal-btn'),
    suggestMovieModal: document.getElementById('suggest-movie-modal'),
    closeSuggestModalBtn: document.getElementById('close-suggest-modal-btn'),
    suggestMovieForm: document.getElementById('suggest-movie-form'),
    suggestTitleInput: document.getElementById('suggest-title-input'),
    suggestAuthorInput: document.getElementById('suggest-author-input'),
  };


// ----------------- Initialization -----------------

  async function init() {
    setupEventListeners();
    await checkCurrentUser();
    updateUserDisplay();
    updateCartUI();
    loadMovies();
    loadProducts();
    loadHistory();
    // Le mini-jeu drag and drop est retiré
  }

  // ----------------- Event Listeners -----------------

  function setupEventListeners() {
    // Navigation Tabs
    elements.navLinks.forEach((link) => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        let tabId = link.dataset.tab;

        if (!tabId) {
          const href = link.getAttribute('href');
          if (href && href.startsWith('#')) {
            const raw = href.substring(1);
            if (raw === 'vote') tabId = 'vote-section';
            else if (raw === 'popcorn') tabId = 'popcorn-section';
            else if (raw === 'history') tabId = 'history-section';
            else tabId = raw;
          }
        }

        if (tabId) switchTab(tabId);
      });
    });

    // Auth Button (Login / Profile)
    if (elements.loginBtn) {
      elements.loginBtn.addEventListener('click', () => {
        openAuthModal('login');
      });
    }

    // Logout Button
    if (elements.logoutBtn) {
      elements.logoutBtn.addEventListener('click', () => {
        handleLogout();
      });
    }

    // Auth Modal Controls
    if (elements.closeAuthModalBtn) {
      elements.closeAuthModalBtn.addEventListener('click', closeAuthModal);
    }
    if (elements.authModal) {
      elements.authModal.addEventListener('click', (e) => {
        if (e.target === elements.authModal) closeAuthModal();
      });
    }
    if (elements.tabLoginBtn) {
      elements.tabLoginBtn.addEventListener('click', () => switchAuthTab('login'));
    }
    if (elements.tabRegisterBtn) {
      elements.tabRegisterBtn.addEventListener('click', () => switchAuthTab('register'));
    }
    if (elements.authForm) {
      elements.authForm.addEventListener('submit', handleAuthSubmit);
    }

    // Cart Drawer Controls
    if (elements.openCartBtn) elements.openCartBtn.addEventListener('click', openCart);
    if (elements.closeCartBtn) elements.closeCartBtn.addEventListener('click', closeCart);
    if (elements.cartBackdrop) elements.cartBackdrop.addEventListener('click', closeCart);
    if (elements.cartBrowseBtn) elements.cartBrowseBtn.addEventListener('click', closeCart);
    if (elements.placeOrderBtn) elements.placeOrderBtn.addEventListener('click', handlePlaceOrder);

    // Success Modal
    if (elements.closeSuccessModalBtn) {
      elements.closeSuccessModalBtn.addEventListener('click', () => {
        if (elements.orderSuccessModal) elements.orderSuccessModal.classList.add('hidden');
      });
    }

    // Genre Filter Buttons
    if (elements.genreFilters) {
      elements.genreFilters.querySelectorAll('.category-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          elements.genreFilters.querySelectorAll('.category-btn').forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          state.activeGenre = btn.dataset.genre || 'all';
          renderMovies();
        });
      });
    }

    // Suggestion Modal — Open / Close
    if (elements.openSuggestModalBtn) {
      elements.openSuggestModalBtn.addEventListener('click', () => {
        if (elements.suggestMovieModal) elements.suggestMovieModal.classList.remove('hidden');
        if (state.username && elements.suggestAuthorInput && !elements.suggestAuthorInput.value) {
          elements.suggestAuthorInput.value = state.username;
        }
      });
    }

    if (elements.closeSuggestModalBtn) {
      elements.closeSuggestModalBtn.addEventListener('click', () => {
        if (elements.suggestMovieModal) elements.suggestMovieModal.classList.add('hidden');
      });
    }

    if (elements.suggestMovieModal) {
      elements.suggestMovieModal.addEventListener('click', (e) => {
        if (e.target === elements.suggestMovieModal) {
          elements.suggestMovieModal.classList.add('hidden');
        }
      });
    }

    // Suggestion Form — Submit
    if (elements.suggestMovieForm) {
      elements.suggestMovieForm.addEventListener('submit', handleSuggestMovieSubmit);
    }

    // TMDB Search Input in Suggestion Modal
    const suggestInput = document.getElementById('suggest-title-input');
    if (suggestInput) {
      suggestInput.addEventListener('input', (e) => {
        clearTimeout(state.searchDebounceTimer);
        const query = e.target.value.trim();

        resetSuggestPreview();

        if (query.length < 2) {
          hideSuggestDropdown();
          return;
        }

        state.searchDebounceTimer = setTimeout(() => {
          fetchTmdbCandidates(query);
        }, 300);
      });
    }

    // Close TMDB dropdown on outside click
    document.addEventListener('click', (e) => {
      const dropdown = document.getElementById('suggest-results-dropdown');
      const input = document.getElementById('suggest-title-input');
      if (dropdown && !dropdown.contains(e.target) && e.target !== input) {
        hideSuggestDropdown();
      }
    });

    // Admin Add Product Button
    if (elements.adminAddProductBtn) {
      elements.adminAddProductBtn.addEventListener('click', openAddProductModal);
    }

    // Admin Product Modal Controls
    if (elements.closeProductModalBtn) {
      elements.closeProductModalBtn.addEventListener('click', closeProductModal);
    }
    if (elements.adminProductModal) {
      elements.adminProductModal.addEventListener('click', (e) => {
        if (e.target === elements.adminProductModal) closeProductModal();
      });
    }
    if (elements.adminProductForm) {
      elements.adminProductForm.addEventListener('submit', handleAdminProductSubmit);
    }

    // Review Modal Controls
    if (elements.closeReviewModalBtn) {
      elements.closeReviewModalBtn.addEventListener('click', closeReviewModal);
    }
    if (elements.reviewModal) {
      elements.reviewModal.addEventListener('click', (e) => {
        if (e.target === elements.reviewModal) closeReviewModal();
      });
    }
    if (elements.reviewForm) {
      elements.reviewForm.addEventListener('submit', handleReviewSubmit);
    }

    // Star Picker in Review Modal
    if (elements.starPicker) {
      elements.starPicker.querySelectorAll('.star-picker-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const rating = parseInt(e.currentTarget.dataset.star, 10);
          setReviewRating(rating);
        });
      });
    }
  }

  // ----------------- Authentication Logic -----------------

  async function checkCurrentUser() {
    if (!state.token) return;
    try {
      const res = await authFetch('/api/auth/me');
      if (res.ok) {
        const data = await res.json();
        state.user = data.user;
        state.username = data.user.username;
        localStorage.setItem('cinema_user', JSON.stringify(data.user));
        localStorage.setItem('cinema_username', data.user.username);
      } else if (res.status === 401) {
        // Token expired / invalid
        handleLogout(false);
      }
    } catch (err) {
      console.warn('Could not verify session with server:', err);
    }
  }

  function openAuthModal(mode = 'login') {
    switchAuthTab(mode);
    if (elements.authErrorBanner) elements.authErrorBanner.classList.add('hidden');
    if (elements.authModal) elements.authModal.classList.remove('hidden');
    if (elements.authUsernameInput) elements.authUsernameInput.focus();
  }

  function closeAuthModal() {
    if (elements.authModal) elements.authModal.classList.add('hidden');
  }

  function switchAuthTab(mode) {
    state.authMode = mode;
    if (elements.authErrorBanner) elements.authErrorBanner.classList.add('hidden');

    if (mode === 'login') {
      if (elements.tabLoginBtn) elements.tabLoginBtn.classList.add('active');
      if (elements.tabRegisterBtn) elements.tabRegisterBtn.classList.remove('active');
      if (elements.authModalTitle) elements.authModalTitle.textContent = 'Connexion Spectateur';
      if (elements.submitAuthBtn) elements.submitAuthBtn.textContent = 'Se connecter';
    } else {
      if (elements.tabRegisterBtn) elements.tabRegisterBtn.classList.add('active');
      if (elements.tabLoginBtn) elements.tabLoginBtn.classList.remove('active');
      if (elements.authModalTitle) elements.authModalTitle.textContent = 'Créer un Compte';
      if (elements.submitAuthBtn) elements.submitAuthBtn.textContent = "S'inscrire";
    }
  }

  async function handleAuthSubmit(e) {
    e.preventDefault();
    const username = elements.authUsernameInput ? elements.authUsernameInput.value.trim() : '';
    const password = elements.authPasswordInput ? elements.authPasswordInput.value : '';

    if (!username || !password) {
      showAuthError('Veuillez renseigner un pseudo et un mot de passe.');
      return;
    }

    const endpoint = state.authMode === 'login' ? '/api/auth/login' : '/api/auth/register';

    try {
      const res = await authFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        showAuthError(data.error || "Erreur lors de l'authentification.");
        return;
      }

      state.token = data.token;
      state.user = data.user;
      state.username = data.user.username;

      localStorage.setItem('cinema_token', data.token);
      localStorage.setItem('cinema_user', JSON.stringify(data.user));
      localStorage.setItem('cinema_username', data.user.username);

      closeAuthModal();
      updateUserDisplay();
      showToast(data.message || `Bienvenue ${state.username} !`, 'success');

      // Refresh views to toggle admin buttons if needed
      renderMovies();
      renderProducts();
      loadHistory();
    } catch (err) {
      console.error(err);
      showAuthError('Erreur de connexion au serveur.');
    }
  }

  function showAuthError(msg) {
    if (!elements.authErrorBanner) return;
    elements.authErrorBanner.textContent = msg;
    elements.authErrorBanner.classList.remove('hidden');
  }

  function handleLogout(showNotification = true) {
    state.token = '';
    state.user = null;
    state.username = '';

    localStorage.removeItem('cinema_token');
    localStorage.removeItem('cinema_user');
    localStorage.removeItem('cinema_username');

    updateUserDisplay();
    renderMovies();
    renderProducts();

    if (showNotification) {
      showToast('Déconnexion réussie. À bientôt !', 'info');
    }
  }

  function updateUserDisplay() {
    if (state.user) {
      const adminBadge = state.isAdmin ? ' Admin' : '';
      const text = `${state.username}${adminBadge}`;
      if (elements.userDisplayName) elements.userDisplayName.textContent = text;
      if (elements.logoutBtn) elements.logoutBtn.classList.remove('hidden');
      if (elements.checkoutNameInput) {
        elements.checkoutNameInput.value = state.username;
        elements.checkoutNameInput.placeholder = '';
      }
    } else {
      if (elements.userDisplayName) elements.userDisplayName.textContent = 'Se connecter';
      if (elements.logoutBtn) elements.logoutBtn.classList.add('hidden');
      if (elements.checkoutNameInput) {
        elements.checkoutNameInput.value = '';
        elements.checkoutNameInput.placeholder = 'Connectez-vous pour passer commande';
      }
    }

    renderProducts();
  }

  // ----------------- TMDB Search Integration -----------------

  async function fetchTmdbCandidates(query) {
    const dropdown = document.getElementById('suggest-results-dropdown');
    if (!dropdown) return;

    try {
      const res = await authFetch(`/api/tmdb/search?query=${encodeURIComponent(query)}`);
      const data = await res.json();
      const results = data.results || [];

      if (results.length === 0) {
        dropdown.innerHTML = `<div class="suggest-no-results">Aucun film trouvé sur TMDB</div>`;
        dropdown.classList.remove('hidden');
        return;
      }

      dropdown.innerHTML = results
        .map(
          (m) => `
        <div class="suggest-result-item" data-tmdb-id="${m.id}">
          <img src="${escapeHtml(m.poster_url)}" alt="${escapeHtml(m.title)}" class="suggest-result-poster" />
          <div class="suggest-result-text">
            <strong>${escapeHtml(m.title)}</strong>
            <span>${m.year || ''}</span>
          </div>
        </div>
      `
        )
        .join('');

      dropdown.classList.remove('hidden');

      dropdown.querySelectorAll('.suggest-result-item').forEach((item, index) => {
        item.addEventListener('click', () => {
          selectTmdbCandidate(results[index]);
        });
      });
    } catch (err) {
      console.error('Erreur recherche TMDB', err);
    }
  }

  function selectTmdbCandidate(movie) {
    state.selectedTmdbMovie = movie;
    hideSuggestDropdown();

    const titleInput = document.getElementById('suggest-title-input');
    const previewContainer = document.getElementById('suggest-preview-container');
    const previewPoster = document.getElementById('suggest-preview-poster');
    const previewTitle = document.getElementById('suggest-preview-title');
    const previewYear = document.getElementById('suggest-preview-year');
    const previewSynopsis = document.getElementById('suggest-preview-synopsis');
    const submitBtn = document.getElementById('submit-suggest-btn');

    if (titleInput) titleInput.value = movie.title;
    if (previewPoster) previewPoster.src = movie.poster_url;
    if (previewTitle) previewTitle.textContent = movie.title;
    if (previewYear) previewYear.textContent = movie.year ? `(${movie.year})` : '';
    if (previewSynopsis) previewSynopsis.textContent = movie.synopsis;

    if (previewContainer) previewContainer.classList.remove('hidden');

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.style.opacity = '1';
      submitBtn.style.cursor = 'pointer';
    }
  }

  function resetSuggestPreview() {
    state.selectedTmdbMovie = null;
    const previewContainer = document.getElementById('suggest-preview-container');
    const submitBtn = document.getElementById('submit-suggest-btn');

    if (previewContainer) previewContainer.classList.add('hidden');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.style.opacity = '0.5';
      submitBtn.style.cursor = 'not-allowed';
    }
  }

  function hideSuggestDropdown() {
    const dropdown = document.getElementById('suggest-results-dropdown');
    if (dropdown) dropdown.classList.add('hidden');
  }

  async function handleSuggestMovieSubmit(e) {
    e.preventDefault();

    if (!state.selectedTmdbMovie) {
      showToast('Veuillez sélectionner un film dans la liste TMDB.', 'error');
      return;
    }

    const authorInput = document.getElementById('suggest-author-input');
    const modal = document.getElementById('suggest-movie-modal');

    const author = (authorInput ? authorInput.value.trim() : '') || state.username || 'Anonyme';

    const payload = {
      title: state.selectedTmdbMovie.title,
      year: state.selectedTmdbMovie.year,
      synopsis: state.selectedTmdbMovie.synopsis,
      poster_url: state.selectedTmdbMovie.poster_url,
      suggested_by: author,
    };

    try {
      const res = await authFetch('/api/movies/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok && !data.already_exists) {
        showToast(data.error || 'Erreur lors de la suggestion.', 'error');
        return;
      }

      if (data.already_exists) {
        showToast(data.message || 'Ce film a déjà été proposé !', 'info');
      } else {
        showToast(data.message || 'Film ajouté aux suggestions !', 'success');
      }

      resetSuggestPreview();
      if (document.getElementById('suggest-title-input')) {
        document.getElementById('suggest-title-input').value = '';
      }
      if (modal) modal.classList.add('hidden');

      loadMovies();
    } catch (err) {
      console.error(err);
      showToast('Erreur de connexion.', 'error');
    }
  }

  // ----------------- Toast Notifications -----------------

  function showToast(message, type = 'info') {
    if (!elements.toastContainer) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';

    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // ----------------- Navigation -----------------

  function switchTab(tabId) {
    elements.navLinks.forEach((link) => {
      const linkTab = link.dataset.tab || (link.getAttribute('href') ? link.getAttribute('href').replace('#', '') : '');
      const isMatch =
        linkTab === tabId ||
        linkTab === tabId.replace('-section', '') ||
        linkTab === tabId.replace('-tab', '') ||
        `${linkTab}-section` === tabId ||
        `${linkTab}-tab` === tabId;

      if (isMatch) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });

    elements.tabPanes.forEach((pane) => {
      const isPaneMatch =
        pane.id === tabId ||
        pane.id === tabId.replace('-section', '') ||
        pane.id === tabId.replace('-tab', '') ||
        `${pane.id}-section` === tabId ||
        `${pane.id}-tab` === tabId;

      if (isPaneMatch) {
        pane.classList.add('active');
        pane.style.display = 'block';
      } else {
        pane.classList.remove('active');
        pane.style.display = 'none';
      }
    });

    if (tabId.includes('vote') || tabId.includes('suggestion')) loadMovies();
    if (tabId.includes('popcorn') || tabId.includes('snack')) loadProducts();
    if (tabId.includes('history')) loadHistory();
  }

  // ----------------- Movies & Suggestions -----------------

  async function loadMovies() {
    try {
      const res = await authFetch('/api/movies');
      const data = await res.json();
      state.movies = data.movies || [];
      renderMovies();
    } catch (err) {
      console.error('Failed to load movies', err);
      if (elements.moviesGrid) {
        elements.moviesGrid.innerHTML = `<div class="empty-state">Impossible de charger les suggestions.</div>`;
      }
    }
  }

  function renderMovies() {
    if (!elements.moviesGrid) return;

    const filteredMovies = state.movies.filter((m) => {
      if (state.activeGenre === 'all') return true;
      return m.genre && m.genre.toLowerCase().includes(state.activeGenre.toLowerCase());
    });

    if (filteredMovies.length === 0) {
      elements.moviesGrid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🎬</div>
          <h3>Aucune suggestion dans ce genre</h3>
          <p>Soyez le premier à proposer un film pour cette catégorie !</p>
        </div>`;
      return;
    }

    elements.moviesGrid.innerHTML = filteredMovies
      .map((m) => {
        const adminControls = state.isAdmin
          ? `
            <div class="admin-movie-actions" style="display: flex; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px dashed rgba(255,255,255,0.1);">
              <button class="btn-utility btn-admin-screen" data-movie-id="${m.id}" data-movie-title="${escapeHtml(m.title)}" style="flex: 2; font-size: 0.78rem; justify-content: center; background: rgba(212, 175, 55, 0.15); border-color: var(--accent-gold); color: var(--accent-gold);">
                Marquer projeté
              </button>
              <button class="btn-utility btn-admin-delete" data-movie-id="${m.id}" data-movie-title="${escapeHtml(m.title)}" style="flex: 1; font-size: 0.78rem; justify-content: center; background: rgba(220, 53, 69, 0.15); border-color: #dc3545; color: #ff6b6b;" title="Supprimer la suggestion">
                Poubelle
              </button>
            </div>
          `
          : '';

        return `
        <div class="movie-card" data-movie-id="${m.id}">
          <div class="movie-poster-wrapper">
            <img src="${escapeHtml(m.poster_url || 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600')}" 
                 alt="${escapeHtml(m.title)}" 
                 class="movie-poster"
                 loading="lazy" />
            <div class="movie-overlay-badges">
              <span class="badge-genre">${escapeHtml(m.genre || 'Suggestion')}</span>
              ${m.runtime ? `<span class="badge-runtime">${escapeHtml(m.runtime)}</span>` : ''}
            </div>
          </div>

          <div class="movie-info">
            <div class="movie-title-row">
              <h3>${escapeHtml(m.title)}</h3>
              <span class="movie-meta">${m.year || ''}</span>
            </div>

            <div class="movie-top-badges">
              ${m.screened_count > 0 ? `<span class="badge-screened"> Projeté (${m.screened_count}x)</span>` : ''}
              ${m.suggested_by ? `<span class="badge-suggested-by"> Proposé par ${escapeHtml(m.suggested_by)}</span>` : ''}
            </div>

            <p class="movie-desc">${escapeHtml(m.synopsis || 'Aucun synopsis disponible.')}</p>

            ${adminControls}
          </div>
        </div>
      `;
      })
      .join('');

    // Wire Admin Actions on Movie Cards
    if (state.isAdmin) {
      elements.moviesGrid.querySelectorAll('.btn-admin-delete').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          const id = e.currentTarget.dataset.movieId;
          const title = e.currentTarget.dataset.movieTitle;
          if (confirm(`Êtes-vous sûr de vouloir supprimer la suggestion « ${title} » ?`)) {
            await handleAdminDeleteMovie(id);
          }
        });
      });

      elements.moviesGrid.querySelectorAll('.btn-admin-screen').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          const id = e.currentTarget.dataset.movieId;
          const title = e.currentTarget.dataset.movieTitle;
          const defaultDate = new Date().toLocaleDateString('fr-FR');
          const date = prompt(`Date ou session de projection pour « ${title} » :`, defaultDate);
          if (date && date.trim()) {
            await handleAdminMoveToHistory(id, date.trim());
          }
        });
      });
    }
  }

  async function handleAdminDeleteMovie(movieId) {
    try {
      const res = await authFetch(`/api/admin/movies/${movieId}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Erreur lors de la suppression.', 'error');
        return;
      }
      showToast(data.message || 'Suggestion supprimée !', 'success');
      loadMovies();
    } catch (err) {
      console.error(err);
      showToast('Erreur réseau.', 'error');
    }
  }

  async function handleAdminMoveToHistory(movieId, screeningDate) {
    try {
      const res = await authFetch(`/api/admin/movies/${movieId}/to-history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ screening_date: screeningDate }),
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Erreur lors de l'ajout à l'historique.", 'error');
        return;
      }
      showToast(data.message || 'Film ajouté à l\'historique des projections !', 'success');
      loadMovies();
      loadHistory();
    } catch (err) {
      console.error(err);
      showToast('Erreur réseau.', 'error');
    }
  }

  // ----------------- Snacks & Concession Stand -----------------

  async function loadProducts() {
    try {
      const res = await authFetch('/api/products');
      const data = await res.json();
      state.products = data.products || [];
      renderProducts();
    } catch (err) {
      console.error('Failed to load products', err);
      if (elements.snacksGrid) {
        elements.snacksGrid.innerHTML = `<div class="empty-state">Impossible de charger le menu popcorn.</div>`;
      }
    }
  }

  const popcornIconSvg = `🍿`;

  function renderProducts() {
    if (!elements.snacksGrid) return;

    // Toggle admin add button visibility
    if (elements.adminAddProductBtn) {
      if (state.isAdmin) {
        elements.adminAddProductBtn.classList.remove('hidden');
      } else {
        elements.adminAddProductBtn.classList.add('hidden');
      }
    }

    const popcornSizes = ['Petit', 'Moyen', 'Grand'];

    const groupedPopcorns = popcornSizes
      .map((size) => {
        const itemsForSize = state.products.filter((p) => p.size === size || p.name.includes(size));
        const prodSucre = itemsForSize.find((p) => p.flavor === 'Sucré' || p.name.toLowerCase().includes('sucré'));
        const prodSale = itemsForSize.find((p) => p.flavor === 'Salé' || p.name.toLowerCase().includes('salé'));

        return {
          size: size,
          price: itemsForSize[0] ? itemsForSize[0].price : 0,
          emoji: itemsForSize[0] ? itemsForSize[0].emoji : popcornIconSvg,
          sucre: prodSucre,
          sale: prodSale,
        };
      })
      .filter((g) => g.sucre || g.sale);

    const otherProducts = state.products.filter(
      (p) => p.category !== 'popcorn' && !popcornSizes.some((s) => p.name.includes(s))
    );

    let html = '';

    html += groupedPopcorns
      .map(
        (group) => `
      <div class="snack-card">
        <div class="snack-header">
          <span class="snack-price-tag">€${group.price.toFixed(2)}</span>
        </div>

        <h3 class="snack-name">${escapeHtml(group.size)}</h3>

        <div class="snack-flavor-actions" style="display: flex; gap: 8px; margin-top: 1rem;">
          ${group.sucre ? `<button class="btn btn-secondary btn-add-snack" data-add-id="${group.sucre.id}" style="flex: 1;">+ Sucré</button>` : ''}
          ${group.sale ? `<button class="btn btn-secondary btn-add-snack" data-add-id="${group.sale.id}" style="flex: 1;">+ Salé</button>` : ''}
        </div>

        ${
          state.isAdmin
            ? `
          <div class="admin-snack-actions" style="display: flex; gap: 6px; margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.1);">
            ${group.sucre ? `<button class="btn-utility btn-edit-product" data-product-id="${group.sucre.id}" style="flex: 1; font-size: 0.75rem; justify-content: center;">✏️ Sucré</button>` : ''}
            ${group.sale ? `<button class="btn-utility btn-edit-product" data-product-id="${group.sale.id}" style="flex: 1; font-size: 0.75rem; justify-content: center;">✏️ Salé</button>` : ''}
          </div>
        `
            : ''
        }
      </div>
    `
      )
      .join('');

    html += otherProducts
      .map(
        (prod) => `
      <div class="snack-card" data-product-id="${prod.id}">
        <div class="snack-header">
          <span class="snack-price-tag">€${prod.price.toFixed(2)}</span>
        </div>
        <h3 class="snack-name">${escapeHtml(prod.name)}</h3>
        <button class="btn btn-secondary btn-add-snack" data-add-id="${prod.id}" style="width: 100%; margin-top: 1rem;">
          + Ajouter au panier
        </button>

        ${
          state.isAdmin
            ? `
          <div class="admin-snack-actions" style="display: flex; gap: 6px; margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.1);">
            <button class="btn-utility btn-edit-product" data-product-id="${prod.id}" style="flex: 2; font-size: 0.75rem; justify-content: center;">✏️ Modifier</button>
            <button class="btn-utility btn-delete-product" data-product-id="${prod.id}" style="flex: 1; font-size: 0.75rem; justify-content: center; color: #ff6b6b; border-color: #dc3545;">🗑️</button>
          </div>
        `
            : ''
        }
      </div>
    `
      )
      .join('');

    elements.snacksGrid.innerHTML = html;

    // Add to cart listeners
    elements.snacksGrid.querySelectorAll('.btn-add-snack').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const prodId = parseInt(e.currentTarget.dataset.addId, 10);
        addToCart(prodId);
      });
    });

    // Admin listeners
    if (state.isAdmin) {
      elements.snacksGrid.querySelectorAll('.btn-edit-product').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const prodId = parseInt(e.currentTarget.dataset.productId, 10);
          openEditProductModal(prodId);
        });
      });

      elements.snacksGrid.querySelectorAll('.btn-delete-product').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          const prodId = parseInt(e.currentTarget.dataset.productId, 10);
          if (confirm('Voulez-vous vraiment supprimer ce produit du catalogue ?')) {
            await handleAdminDeleteProduct(prodId);
          }
        });
      });
    }
  }

  function openAddProductModal() {
    if (elements.adminProductForm) elements.adminProductForm.reset();
    if (elements.adminProductId) elements.adminProductId.value = '';
    if (elements.adminProductModalTitle) elements.adminProductModalTitle.textContent = 'Nouveau Produit';
    if (elements.adminProductModal) elements.adminProductModal.classList.remove('hidden');
  }

  function openEditProductModal(productId) {
    const prod = state.products.find((p) => p.id === productId);
    if (!prod) return;

    if (elements.adminProductId) elements.adminProductId.value = prod.id;
    if (elements.adminProductName) elements.adminProductName.value = prod.name;
    if (elements.adminProductPrice) elements.adminProductPrice.value = prod.price;
    if (elements.adminProductCategory) elements.adminProductCategory.value = prod.category || 'popcorn';
    if (elements.adminProductFlavor) elements.adminProductFlavor.value = prod.flavor || '';
    if (elements.adminProductSize) elements.adminProductSize.value = prod.size || '';
    if (elements.adminProductEmoji) elements.adminProductEmoji.value = prod.emoji || '🍿';

    if (elements.adminProductModalTitle) {
      elements.adminProductModalTitle.textContent = `Modifier « ${prod.name} »`;
    }

    if (elements.adminProductModal) elements.adminProductModal.classList.remove('hidden');
  }

  function closeProductModal() {
    if (elements.adminProductModal) elements.adminProductModal.classList.add('hidden');
  }

  async function handleAdminProductSubmit(e) {
    e.preventDefault();

    const id = elements.adminProductId ? elements.adminProductId.value : '';
    const name = elements.adminProductName ? elements.adminProductName.value.trim() : '';
    const price = elements.adminProductPrice ? parseFloat(elements.adminProductPrice.value) : 0;
    const category = elements.adminProductCategory ? elements.adminProductCategory.value : 'popcorn';
    const flavor = elements.adminProductFlavor ? elements.adminProductFlavor.value.trim() : '';
    const size = elements.adminProductSize ? elements.adminProductSize.value.trim() : '';
    const emoji = elements.adminProductEmoji ? elements.adminProductEmoji.value.trim() : '🍿';

    if (!name || isNaN(price)) {
      showToast('Veuillez renseigner un nom et un prix valide.', 'error');
      return;
    }

    const payload = { name, price, category, flavor, size, emoji };

    try {
      let res;
      if (id) {
        // Update product
        res = await authFetch(`/api/admin/products/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        // Create product
        res = await authFetch('/api/admin/products', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Erreur lors de la sauvegarde du produit.', 'error');
        return;
      }

      showToast(data.message || 'Produit enregistré avec succès !', 'success');
      closeProductModal();
      loadProducts();
    } catch (err) {
      console.error(err);
      showToast('Erreur réseau.', 'error');
    }
  }

  async function handleAdminDeleteProduct(productId) {
    try {
      const res = await authFetch(`/api/admin/products/${productId}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Erreur lors de la suppression.', 'error');
        return;
      }
      showToast(data.message || 'Produit supprimé !', 'success');
      loadProducts();
    } catch (err) {
      console.error(err);
      showToast('Erreur réseau.', 'error');
    }
  }

  // ----------------- Cart Management -----------------

  function addToCart(productId) {
    const product = state.products.find((p) => p.id === productId);
    if (!product) return;

    const existing = state.cart.find((it) => it.product_id === productId);
    if (existing) {
      existing.quantity += 1;
    } else {
      state.cart.push({
        product_id: product.id,
        name: product.name,
        price: product.price,
        emoji: product.emoji || popcornIconSvg,
        quantity: 1,
      });
    }

    saveCart();
    updateCartUI();
    showToast(`Ajouté : 1x ${product.name}`, 'info');
  }

  function updateQuantity(productId, delta) {
    const item = state.cart.find((it) => it.product_id === productId);
    if (!item) return;

    item.quantity += delta;
    if (item.quantity <= 0) {
      state.cart = state.cart.filter((it) => it.product_id !== productId);
    }

    saveCart();
    updateCartUI();
  }

  function saveCart() {
    localStorage.setItem('cinema_cart', JSON.stringify(state.cart));
  }

  function updateCartUI() {
    const totalCount = state.cart.reduce((sum, it) => sum + it.quantity, 0);
    const totalPrice = state.cart.reduce((sum, it) => sum + it.price * it.quantity, 0);

    if (elements.headerCartCount) elements.headerCartCount.textContent = totalCount;
    if (elements.cartTotalDisplay) elements.cartTotalDisplay.textContent = `€${totalPrice.toFixed(2)}`;

    // Show/hide the floating cart button
    if (elements.openCartBtn) {
      if (totalCount > 0) {
        elements.openCartBtn.classList.remove('hidden');
      } else {
        elements.openCartBtn.classList.add('hidden');
      }
    }

    if (elements.placeOrderBtn) elements.placeOrderBtn.disabled = totalCount === 0;

    if (!elements.cartItemsList) return;

    if (state.cart.length === 0) {
      elements.cartItemsList.innerHTML = `
        <div class="empty-cart-message">
          <span>🍿</span>
          <p>Votre panier de popcorn est vide.</p>
        </div>
      `;
    } else {
      elements.cartItemsList.innerHTML = state.cart
        .map(
          (it) => `
        <div class="cart-item-row">
          <div class="cart-item-info">
          <div class="cart-item-title" style="font-weight: 600;">${escapeHtml(it.name)}</div>
          <div class="cart-item-price">€${(it.price * it.quantity).toFixed(2)} · €${it.price.toFixed(2)} / u</div>
          </div>
          <div class="cart-qty-controls">
            <button class="qty-btn btn-qty-minus" data-qty-id="${it.product_id}" data-delta="-1">−</button>
            <span class="cart-item-qty">${it.quantity}</span>
            <button class="qty-btn btn-qty-plus" data-qty-id="${it.product_id}" data-delta="1">+</button>
            <button class="btn-remove-item" data-remove-id="${it.product_id}" title="Supprimer">🗑</button>
          </div>
        </div>
      `
        )
        .join('');

      // Écouteurs pour ajuster la quantité (- et +)
      elements.cartItemsList.querySelectorAll('.qty-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const id = parseInt(e.currentTarget.dataset.qtyId, 10);
          const delta = parseInt(e.currentTarget.dataset.delta, 10);
          updateQuantity(id, delta);
        });
      });

      // Écouteur pour la suppression complète
      elements.cartItemsList.querySelectorAll('.btn-remove-item').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const id = parseInt(e.currentTarget.dataset.removeId, 10);
          removeFromCart(id);
        });
      });
    }
  }

  function removeFromCart(productId) {
    state.cart = state.cart.filter((it) => it.product_id !== productId);
    saveCart();
    updateCartUI();
    showToast('Produit retiré du panier', 'info');
  }

  function openCart() {
    if (state.username && elements.checkoutNameInput && !elements.checkoutNameInput.value) {
      elements.checkoutNameInput.value = state.username;
    }
    if (elements.cartBackdrop) elements.cartBackdrop.classList.remove('hidden');
    if (elements.cartDrawer) elements.cartDrawer.classList.add('open');
  }

  function closeCart() {
    if (elements.cartBackdrop) elements.cartBackdrop.classList.add('hidden');
    if (elements.cartDrawer) elements.cartDrawer.classList.remove('open');
  }

  async function handlePlaceOrder() {
    // 1. Vérification de la connexion de l'utilisateur
    if (!state.user || !state.token) {
      showToast('Vous devez être connecté pour passer une commande !', 'info');
      openAuthModal('login');
      return;
    }

    if (state.cart.length === 0) {
      showToast('Votre panier est vide.', 'error');
      return;
    }

    // 2. Récupération du mode de paiement sélectionné
    const paymentRadio = document.querySelector('input[name="payment-method"]:checked');
    const paymentMethod = paymentRadio ? paymentRadio.value : 'carte';

    if (elements.placeOrderBtn) {
      elements.placeOrderBtn.disabled = true;
      elements.placeOrderBtn.textContent = 'Génération de la commande...';
    }

    try {
      const payload = {
        customer_name: state.username,
        payment_method: paymentMethod,
        items: state.cart.map((it) => ({
          product_id: it.product_id,
          quantity: it.quantity,
        })),
      };

      const res = await authFetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Erreur lors de la commande.', 'error');
        if (elements.placeOrderBtn) {
          elements.placeOrderBtn.disabled = false;
          elements.placeOrderBtn.textContent = 'Valider et payer';
        }
        return;
      }

      const order = data.order;
      state.cart = [];
      saveCart();
      updateCartUI();
      closeCart();

      if (elements.successOrderCode) elements.successOrderCode.textContent = order.order_code;
      if (elements.successCustomerName) elements.successCustomerName.textContent = order.customer_name;
      if (elements.successTotalPrice) elements.successTotalPrice.textContent = `€${order.total_price.toFixed(2)}`;
      if (elements.successItemsList) {
        elements.successItemsList.innerHTML = order.items
          .map(
            (it) => `
          <div class="ticket-detail-row">
            <span>${it.quantity}x ${escapeHtml(it.product_name)}</span>
            <span>€${(it.unit_price * it.quantity).toFixed(2)}</span>
          </div>
        `
          )
          .join('');
      }

      showToast(`Commande passée (Paiement : ${paymentMethod.toUpperCase()})`, 'success');
      if (elements.orderSuccessModal) elements.orderSuccessModal.classList.remove('hidden');
    } catch (err) {
      console.error(err);
      showToast('Erreur réseau lors de la commande.', 'error');
    } finally {
      if (elements.placeOrderBtn) {
        elements.placeOrderBtn.disabled = false;
        elements.placeOrderBtn.textContent = 'Valider et payer';
      }
    }
  }

// Helper : Vérifie si la date de projection est dans la semaine en cours (du Lundi au Dimanche)
function isScreeningInCurrentWeek(dateStr) {
  if (!dateStr) return false;

  let screeningDate;

  // Prise en charge des formats "JJ/MM/AA", "JJ/MM/AAAA" ou "AAAA-MM-JJ"
  if (typeof dateStr === 'string' && dateStr.includes('/')) {
    const parts = dateStr.split('/');
    if (parts.length === 3) {
      const day = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1; // Les mois vont de 0 à 11 en JS
      let year = parseInt(parts[2], 10);
      if (year < 100) year += 2000;
      screeningDate = new Date(year, month, day);
    }
  } else {
    screeningDate = new Date(dateStr);
  }

  if (!screeningDate || isNaN(screeningDate.getTime())) return false;

  const now = new Date();

  // Calcul du Lundi 00:00:00 et du Dimanche 23:59:59 de la semaine actuelle
  const dayOfWeek = now.getDay(); // 0 = Dimanche, 1 = Lundi, ...
  const distanceToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;

  const monday = new Date(now);
  monday.setDate(now.getDate() + distanceToMonday);
  monday.setHours(0, 0, 0, 0);

  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  sunday.setHours(23, 59, 59, 999);

  return screeningDate >= monday && screeningDate <= sunday;
}

  // ----------------- Historique des Projections (LetterboCS) -----------------

  async function loadHistory() {
    const container = elements.historyList;
    if (!container) return;

    try {
      const res = await authFetch('/api/history');
      const data = await res.json();
      state.screenings = data.screenings || [];
      renderHistory();
    } catch (err) {
      console.error('Erreur chargement historique', err);
      container.innerHTML = `<div class="empty-state">Impossible de charger l'historique des projections.</div>`;
    }
  }

function renderHistory() {
    const container = elements.historyList;
    if (!container) return;

    if (state.screenings.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📽️</div>
          <h3>Aucun film dans l'historique pour l'instant</h3>
        </div>`;
      return;
    }

    container.innerHTML = state.screenings
      .map((item) => {
        const avg = item.avg_rating || 0;
        const reviewCount = item.review_count || 0;
        const starsFull = Math.round(avg);
        const starsStr = avg > 0 ? '★'.repeat(starsFull) + '☆'.repeat(5 - starsFull) : '☆☆☆☆☆';

        // 1. Génération conditionnelle de la date (rien si elle est absente ou vide)
        const dateHtml = item.screening_date && item.screening_date.trim() !== ''
          ? `<span class="history-date">${escapeHtml(item.screening_date)}</span>`
          : '';

        // Vérification si la projection a lieu cette semaine
        const isThisWeek = isScreeningInCurrentWeek(item.screening_date);

        const buttonHtml = `<button class="btn-suggest-primary btn-rate-movie" data-movie-id="${item.movie_id}" data-movie-title="${escapeHtml(item.title)}" style="font-size: 0.82rem; padding: 6px 14px;">
          Donner mon avis
        </button>`;

        const wordsHtml =
          item.words && item.words.length > 0
            ? item.words
                .map(
                  (w) =>
                    `<span class="history-word-tag">${escapeHtml(w.word)} ${w.count > 1 ? `(${w.count})` : ''}</span>`
                )
                .join('')
            : `<span style="color: var(--text-muted); font-size: 0.8rem; font-style: italic;">Pas encore de mots partagés.</span>`;

        return `
        <div class="history-card" data-screening-id="${item.screening_id}" data-movie-id="${item.movie_id}">
          <div class="history-header">
            <h3 class="history-movie-title">${escapeHtml(item.title)}</h3>
            <div class="history-header-right">
              ${dateHtml}
              ${buttonHtml}
            </div>
          </div>

          <div class="history-rating-row">
            <span class="history-stars">${starsStr}</span>
            <span class="history-score">${avg > 0 ? `${avg.toFixed(1)} / 5.0` : ''}</span>
            <span style="color: var(--text-muted); font-size: 0.85rem;">(${reviewCount})</span>
          </div>

          <div class="history-wordcloud-box" style="margin-top: 12px;">
            <div class="wordcloud-tags-container" style="display: flex; flex-wrap: wrap; gap: 6px;">
              ${wordsHtml}
            </div>
          </div>
        </div>
        `;
      })
      .join('');

    // Attachement de l'événement uniquement sur les boutons affichés
    container.querySelectorAll('.btn-rate-movie').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const movieId = e.currentTarget.dataset.movieId;
        const title = e.currentTarget.dataset.movieTitle;
        openReviewModal(movieId, title);
      });
    });
  }

  function openReviewModal(movieId, movieTitle) {
    if (!state.token) {
      showToast('Veuillez vous connecter pour noter un film !', 'info');
      openAuthModal('login');
      return;
    }

    if (elements.reviewMovieId) elements.reviewMovieId.value = movieId;
    if (elements.reviewMovieTitle) elements.reviewMovieTitle.textContent = `Avis sur « ${movieTitle} »`;
    if (elements.reviewTextInput) elements.reviewTextInput.value = '';
    if (elements.reviewWordInput) elements.reviewWordInput.value = '';

    setReviewRating(5);

    if (elements.reviewModal) elements.reviewModal.classList.remove('hidden');
  }

  function closeReviewModal() {
    if (elements.reviewModal) elements.reviewModal.classList.add('hidden');
  }

  function setReviewRating(rating) {
    state.selectedReviewRating = rating;
    if (elements.reviewRatingValue) elements.reviewRatingValue.value = rating;
    if (elements.starPickerLabel) elements.starPickerLabel.textContent = `${rating}.0 / 5`;

    if (!elements.starPicker) return;

    elements.starPicker.querySelectorAll('.star-picker-btn').forEach((star) => {
      const starVal = parseInt(star.dataset.star, 10);
      if (starVal <= rating) {
        star.classList.add('selected');
      } else {
        star.classList.remove('selected');
      }
    });
  }

  async function handleReviewSubmit(e) {
    e.preventDefault();

    const movieId = elements.reviewMovieId ? parseInt(elements.reviewMovieId.value, 10) : null;
    const rating = state.selectedReviewRating || 5;
    const reviewText = elements.reviewTextInput ? elements.reviewTextInput.value.trim() : '';
    const word = elements.reviewWordInput ? elements.reviewWordInput.value.trim() : '';

    if (!movieId) {
      showToast('Film introuvable.', 'error');
      return;
    }

    try {
      // 1. Submit review & rating
      const reviewPayload = {
        movie_id: movieId,
        reviewer_name: state.username,
        rating: rating,
        review_text: reviewText || undefined,
      };

      const res = await authFetch('/api/reviews', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reviewPayload),
      });

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || "Erreur lors de l'envoi de votre avis.", 'error');
        return;
      }

      // 2. Submit word to cloud if filled
      if (word) {
        await authFetch('/api/wordcloud', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            movie_id: movieId,
            word: word,
            contributor_name: state.username,
          }),
        });
      }

      showToast(data.message || 'Merci pour votre avis !', 'success');
      closeReviewModal();
      loadHistory();
    } catch (err) {
      console.error(err);
      showToast('Erreur réseau.', 'error');
    }
  }

  // ----------------- Entry Point -----------------

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
