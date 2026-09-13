/* ==========================================================
   CinéClub Student Association - Client Application Logic
   ========================================================== */

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
    username: localStorage.getItem('cinema_username') || '',
    votedMovieId: localStorage.getItem('cinema_voted_movie_id') || null,
    cart: JSON.parse(localStorage.getItem('cinema_cart') || '[]'),
    myOrders: JSON.parse(localStorage.getItem('cinema_my_orders') || '[]'),
    adminPin: sessionStorage.getItem('cinema_admin_pin') || null,
    showStandings: true,
    activeCategory: 'all',
    activeGenre: 'all',
    movies: [],
    products: [],
    adminOrdersCache: [],
    adminPollInterval: null,
    wordCloudPollInterval: null,

    // Letterboxd & Wooclap states
    selectedReviewMovieId: null,
    selectedWordCloudMovieId: null,
    currentRating: 5.0,
  };

  // DOM Elements
  const elements = {
    // Navigation (supports both traditional links and film strip frame buttons)
    navLinks: document.querySelectorAll('.nav-link, .film-frame'),
    tabPanes: document.querySelectorAll('.tab-pane, .tab-content, section[id]'),
    loginBtn: document.getElementById('loginBtn'),
    userDisplayName: document.getElementById('user-display-name') || document.querySelector('#loginBtn span'),
    userPillContainer: document.getElementById('user-pill-container'),
    voterNameInput: document.getElementById('voter-name-input'),
    saveUsernameBtn: document.getElementById('save-username-btn'),
    myOrdersBadge: document.getElementById('my-orders-badge'),

    // Voting
    moviesGrid: document.getElementById('movies-grid') || document.querySelector('.movie-grid'),
    totalVotesCount: document.getElementById('total-votes-count'),
    leadingMovieTitle: document.getElementById('leading-movie-title'),
    togglePercentagesCheck: document.getElementById('toggle-percentages-check'),

    // Snacks & Cart
    snacksGrid: document.getElementById('snacks-grid') || document.querySelector('.snack-grid'),
    categoryFilters: document.getElementById('category-filters'),
    openCartBtn: document.getElementById('cartBtn') || document.getElementById('open-cart-btn'),
    closeCartBtn: document.getElementById('close-cart-btn'),
    cartBackdrop: document.getElementById('cart-backdrop'),
    cartDrawer: document.getElementById('cart-drawer'),
    cartItemsList: document.getElementById('cart-items-list'),
    cartTotalDisplay: document.getElementById('cart-total-display'),
    headerCartCount: document.getElementById('cartCount') || document.getElementById('header-cart-count'),
    checkoutNameInput: document.getElementById('checkout-name-input'),
    placeOrderBtn: document.getElementById('place-order-btn'),
    cartBrowseBtn: document.getElementById('cart-browse-btn'),

    // Success Modal
    orderSuccessModal: document.getElementById('order-success-modal'),
    closeSuccessModalBtn: document.getElementById('close-success-modal-btn'),
    successOrderCode: document.getElementById('success-order-code'),
    successCustomerName: document.getElementById('success-customer-name'),
    successTotalPrice: document.getElementById('success-total-price'),
    successItemsList: document.getElementById('success-items-list'),

    // Passes
    ticketsContainer: document.getElementById('tickets-container'),
    orderLookupName: document.getElementById('order-lookup-name'),
    refreshOrdersBtn: document.getElementById('refresh-orders-btn'),
    goToSnacksBtn: document.getElementById('go-to-snacks-btn'),

    // Letterboxd Reviews
    reviewsMovieSelect: document.getElementById('reviews-movie-select'),
    reviewsAvgScore: document.getElementById('reviews-avg-score'),
    reviewsStarsVisual: document.getElementById('reviews-stars-visual'),
    reviewsTotalCount: document.getElementById('reviews-total-count'),
    composeReviewForm: document.getElementById('compose-review-form'),
    starPicker: document.getElementById('star-picker'),
    starRatingText: document.getElementById('star-rating-text'),
    reviewAuthorInput: document.getElementById('review-author-input'),
    reviewTextInput: document.getElementById('review-text-input'),
    submitReviewBtn: document.getElementById('submit-review-btn'),
    reviewsFeed: document.getElementById('reviews-feed'),
    feedReviewCount: document.getElementById('feed-review-count'),

    // Wooclap Word Cloud
    wordcloudMovieSelect: document.getElementById('wordcloud-movie-select'),
    wordcloudWordInput: document.getElementById('wordcloud-word-input'),
    submitWordBtn: document.getElementById('submit-word-btn'),
    wordcloudArena: document.getElementById('wordcloud-arena'),
    wordcloudStage: document.getElementById('wordcloud-stage'),
    wordcloudTotalSubmissions: document.getElementById('wordcloud-total-submissions'),
    refreshWordcloudBtn: document.getElementById('refresh-wordcloud-btn'),

    // Admin
    adminLockScreen: document.getElementById('admin-lock-screen'),
    adminDashboard: document.getElementById('admin-dashboard'),
    adminPinInput: document.getElementById('admin-pin-input'),
    adminLoginBtn: document.getElementById('admin-login-btn'),
    adminLogoutBtn: document.getElementById('admin-logout-btn'),
    adminRefreshBtn: document.getElementById('admin-refresh-btn'),
    adminResetEventBtn: document.getElementById('admin-reset-event-btn'),
    kpiAttendees: document.getElementById('kpi-attendees'),
    kpiAttendeesDetail: document.getElementById('kpi-attendees-detail'),
    kpiVotes: document.getElementById('kpi-votes'),
    kpiOrders: document.getElementById('kpi-orders'),
    kpiPendingOrders: document.getElementById('kpi-pending-orders'),
    kpiRevenue: document.getElementById('kpi-revenue'),
    kpiPaidRevenue: document.getElementById('kpi-paid-revenue'),
    adminOrdersTbody: document.getElementById('admin-orders-tbody'),
    adminOrderFilter: document.getElementById('admin-order-filter'),
    addMovieForm: document.getElementById('add-movie-form'),
    topSnacksList: document.getElementById('top-snacks-list'),

    // Toast
    toastContainer: document.getElementById('toast-container'),

    // Suggestion Modal
    openSuggestModalBtn: document.getElementById('open-suggest-modal-btn'),
    suggestMovieModal: document.getElementById('suggest-movie-modal'),
    closeSuggestModalBtn: document.getElementById('close-suggest-modal-btn'),
    suggestMovieForm: document.getElementById('suggest-movie-form'),
    suggestTitleInput: document.getElementById('suggest-title-input'),
    suggestGenreSelect: document.getElementById('suggest-genre-select'),
    suggestYearInput: document.getElementById('suggest-year-input'),
    suggestSynopsisInput: document.getElementById('suggest-synopsis-input'),
    suggestAuthorInput: document.getElementById('suggest-author-input'),

    // Genre Filters
    genreFilters: document.getElementById('genre-filters'),
  };

  // ----------------- Initialization -----------------

  function init() {
    setupEventListeners();
    initStarPicker();
    updateUserDisplay();
    updateCartUI();
    loadMovies();
    loadProducts();
    loadMyOrders();

    if (state.adminPin) {
      verifyAdminPin(state.adminPin);
    }
  }

  // ----------------- Event Listeners -----------------

  function setupEventListeners() {
    // Navigation Tabs & Film Strip Buttons (Rolls to center the selected frame)
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

        // Vintage film rolling animation: roll/scroll clicked frame to the center of the film strip
        link.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });

        if (tabId) switchTab(tabId);
      });
    });

    // Login / User Identity Button
    if (elements.loginBtn) {
      elements.loginBtn.addEventListener('click', () => {
        const current = state.username || '';
        const name = prompt('Entrez votre prénom ou pseudo :', current);
        if (name !== null && name.trim()) {
          setUsername(name);
        }
      });
    }

    // Save Username Button
    if (elements.saveUsernameBtn) {
      elements.saveUsernameBtn.addEventListener('click', () => {
        const val = elements.voterNameInput ? elements.voterNameInput.value : '';
        setUsername(val);
      });
    }
    if (elements.voterNameInput) {
      elements.voterNameInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') setUsername(elements.voterNameInput.value);
      });
    }

    // Toggle Percentage Display
    if (elements.togglePercentagesCheck) {
      elements.togglePercentagesCheck.addEventListener('change', (e) => {
        state.showStandings = e.target.checked;
        renderMovies();
      });
    }

    // Category Filters
    if (elements.categoryFilters) {
      elements.categoryFilters.querySelectorAll('.category-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          elements.categoryFilters.querySelectorAll('.category-btn').forEach((b) => b.classList.remove('active'));
          btn.classList.add('active');
          state.activeCategory = btn.dataset.category || 'all';
          renderProducts();
        });
      });
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

    // Passes / Orders Tab
    if (elements.refreshOrdersBtn) elements.refreshOrdersBtn.addEventListener('click', loadMyOrders);
    if (elements.goToSnacksBtn) elements.goToSnacksBtn.addEventListener('click', () => switchTab('snacks-tab'));
    if (elements.orderLookupName) {
      elements.orderLookupName.addEventListener('change', loadMyOrders);
      elements.orderLookupName.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loadMyOrders();
      });
    }

    // Reviews Tab
    if (elements.reviewsMovieSelect) {
      elements.reviewsMovieSelect.addEventListener('change', (e) => {
        state.selectedReviewMovieId = e.target.value;
        loadReviews(state.selectedReviewMovieId);
      });
    }
    if (elements.composeReviewForm) {
      elements.composeReviewForm.addEventListener('submit', (e) => {
        e.preventDefault();
        submitReview();
      });
    } else if (elements.submitReviewBtn) {
      elements.submitReviewBtn.addEventListener('click', submitReview);
    }

    // Wordcloud Tab
    if (elements.wordcloudMovieSelect) {
      elements.wordcloudMovieSelect.addEventListener('change', (e) => {
        state.selectedWordCloudMovieId = e.target.value;
        loadWordCloud(state.selectedWordCloudMovieId);
      });
    }
    if (elements.submitWordBtn) elements.submitWordBtn.addEventListener('click', submitWord);
    if (elements.wordcloudWordInput) {
      elements.wordcloudWordInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') submitWord();
      });
    }
    if (elements.refreshWordcloudBtn) {
      elements.refreshWordcloudBtn.addEventListener('click', () => {
        loadWordCloud(state.selectedWordCloudMovieId);
      });
    }

    // Admin Panel
    if (elements.adminLoginBtn) elements.adminLoginBtn.addEventListener('click', handleAdminLogin);
    if (elements.adminPinInput) {
      elements.adminPinInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleAdminLogin();
      });
    }
    if (elements.adminLogoutBtn) elements.adminLogoutBtn.addEventListener('click', handleAdminLogout);
    if (elements.adminRefreshBtn) elements.adminRefreshBtn.addEventListener('click', loadAdminDashboardData);
    if (elements.adminResetEventBtn) elements.adminResetEventBtn.addEventListener('click', handleResetEvent);
    if (elements.adminOrderFilter) {
      elements.adminOrderFilter.addEventListener('change', () => {
        renderAdminOrdersTable(state.adminOrdersCache);
      });
    }
    if (elements.addMovieForm) elements.addMovieForm.addEventListener('submit', handleAddMovie);

    // Genre Filter Buttons (Vos Suggestions section)
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

    // Suggestion Modal — Open
    if (elements.openSuggestModalBtn) {
      elements.openSuggestModalBtn.addEventListener('click', () => {
        if (elements.suggestMovieModal) elements.suggestMovieModal.classList.remove('hidden');
        // Pre-fill author name if user is logged in
        if (state.username && elements.suggestAuthorInput && !elements.suggestAuthorInput.value) {
          elements.suggestAuthorInput.value = state.username;
        }
      });
    }

    // Suggestion Modal — Close
    if (elements.closeSuggestModalBtn) {
      elements.closeSuggestModalBtn.addEventListener('click', () => {
        if (elements.suggestMovieModal) elements.suggestMovieModal.classList.add('hidden');
      });
    }

    // Suggestion Modal — Close on backdrop click
    if (elements.suggestMovieModal) {
      elements.suggestMovieModal.addEventListener('click', (e) => {
        if (e.target === elements.suggestMovieModal) {
          elements.suggestMovieModal.classList.add('hidden');
        }
      });
    }

    // Suggestion Form — Submit
    if (elements.suggestMovieForm) {
      elements.suggestMovieForm.addEventListener('submit', handleSuggestMovie);
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

  // ----------------- User Identity -----------------

  function updateUserDisplay() {
    const displayName = state.username || 'Se connecter';
    if (elements.userDisplayName) elements.userDisplayName.textContent = displayName;
    if (elements.loginBtn) {
      const span = elements.loginBtn.querySelector('span');
      if (span) span.textContent = displayName;
    }
    if (state.username) {
      if (elements.voterNameInput) elements.voterNameInput.value = state.username;
      if (elements.checkoutNameInput) elements.checkoutNameInput.value = state.username;
      if (elements.orderLookupName) elements.orderLookupName.value = state.username;
      if (elements.reviewAuthorInput) elements.reviewAuthorInput.value = state.username;
    }
  }

  function setUsername(name) {
    const trimmed = (name || '').trim();
    if (!trimmed) {
      showToast('Veuillez entrer un prénom ou pseudo valide.', 'error');
      return false;
    }
    state.username = trimmed;
    localStorage.setItem('cinema_username', trimmed);
    updateUserDisplay();
    showToast(`Bienvenue, ${trimmed} !`, 'success');
    return true;
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
        `${linkTab}-tab` === tabId ||
        ((linkTab === 'vote' || linkTab === 'frame-vote') && (tabId === 'vote-section' || tabId === 'voting-tab' || tabId === 'vote')) ||
        ((linkTab === 'popcorn' || linkTab === 'frame-popcorn') && (tabId === 'popcorn-section' || tabId === 'snacks-tab' || tabId === 'popcorn')) ||
        ((linkTab === 'history' || linkTab === 'frame-history') && (tabId === 'history-section' || tabId === 'ticket-tab' || tabId === 'history'));

      if (isMatch) {
        link.classList.add('active');
        // Roll to center the selected frame in view
        link.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
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
        `${pane.id}-tab` === tabId ||
        ((pane.id === 'vote-section' || pane.id === 'voting-tab') && (tabId === 'vote' || tabId === 'vote-section' || tabId === 'voting-tab')) ||
        ((pane.id === 'popcorn-section' || pane.id === 'snacks-tab') && (tabId === 'popcorn' || tabId === 'popcorn-section' || tabId === 'snacks-tab')) ||
        ((pane.id === 'history-section' || pane.id === 'ticket-tab') && (tabId === 'history' || tabId === 'history-section' || tabId === 'ticket-tab'));

      if (isPaneMatch) {
        pane.classList.add('active');
        pane.style.display = 'block';
      } else {
        pane.classList.remove('active');
        pane.style.display = 'none';
      }
    });

    // Handle background polling states
    if (tabId === 'admin-tab' && state.adminPin) {
      loadAdminDashboardData();
      startAdminPolling();
    } else {
      stopAdminPolling();
    }

    if (tabId === 'wordcloud-tab') {
      loadWordCloud(state.selectedWordCloudMovieId);
      startWordCloudPolling();
    } else {
      stopWordCloudPolling();
    }

    // Refresh tab-specific data
    if (tabId.includes('vote')) loadMovies();
    if (tabId.includes('popcorn') || tabId.includes('snack')) loadProducts();
    if (tabId === 'reviews-tab') loadReviews(state.selectedReviewMovieId);
  }

  // ----------------- Movies & Voting -----------------

  async function loadMovies() {
    try {
      const res = await fetch('/api/movies');
      const data = await res.json();
      state.movies = data.movies || [];

      if (elements.totalVotesCount) {
        elements.totalVotesCount.textContent = data.total_votes || 0;
      }
      if (elements.leadingMovieTitle) {
        if (state.movies.length > 0 && data.total_votes > 0) {
          elements.leadingMovieTitle.textContent = `${state.movies[0].title} (${state.movies[0].percentage}%)`;
        } else {
          elements.leadingMovieTitle.textContent = 'No votes yet';
        }
      }

      renderMovies();
      updateMovieDropdowns();
    } catch (err) {
      console.error('Failed to load movies', err);
      if (elements.moviesGrid) {
        elements.moviesGrid.innerHTML = `<div class="empty-state">Failed to load movies. Server error.</div>`;
      }
    }
  }

  function updateMovieDropdowns() {
    if (!state.movies || state.movies.length === 0) return;

    const optionsHtml = state.movies
      .map((m) => `<option value="${m.id}">${escapeHtml(m.title)} (${m.year || ''})</option>`)
      .join('');

    if (elements.reviewsMovieSelect) {
      elements.reviewsMovieSelect.innerHTML = optionsHtml;
      if (!state.selectedReviewMovieId || !state.movies.some((m) => String(m.id) === String(state.selectedReviewMovieId))) {
        state.selectedReviewMovieId = state.movies[0].id;
      }
      elements.reviewsMovieSelect.value = state.selectedReviewMovieId;
    }

    if (elements.wordcloudMovieSelect) {
      elements.wordcloudMovieSelect.innerHTML = optionsHtml;
      if (!state.selectedWordCloudMovieId || !state.movies.some((m) => String(m.id) === String(state.selectedWordCloudMovieId))) {
        state.selectedWordCloudMovieId = state.movies[0].id;
      }
      elements.wordcloudMovieSelect.value = state.selectedWordCloudMovieId;
    }
  }

  function renderMovies() {
    if (!elements.moviesGrid) return;

    // Filtrer selon le genre sélectionné
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
      .map((m) => `
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
              ${m.screened_count > 0 ? `<span class="badge-screened">🍿 Projeté ${m.screened_count}x</span>` : ''}
              ${m.suggested_by ? `<span class="badge-suggested-by">💡 Proposé par ${escapeHtml(m.suggested_by)}</span>` : ''}
            </div>

            <p class="movie-desc">${escapeHtml(m.synopsis || 'Aucun synopsis disponible.')}</p>
          </div>
        </div>
      `)
      .join('');
  }

  // ----------------- Suggest a Movie -----------------

  async function handleSuggestMovieSubmit(e) {
    e.preventDefault();

    const titleInput = document.getElementById('suggest-title-input');
    const authorInput = document.getElementById('suggest-author-input');
    const modal = document.getElementById('suggest-movie-modal');

    const title = titleInput ? titleInput.value.trim() : '';
    if (!title) {
      showToast('Le titre du film est obligatoire.', 'error');
      return;
    }

    const payload = {
      title: title,
      suggested_by: authorInput ? authorInput.value.trim() : state.username,
    };

    if (payload.suggested_by) {
      setUsername(payload.suggested_by);
    }

    try {
      const res = await fetch('/api/movies/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Erreur lors de la suggestion.', 'error');
        return;
      }

      showToast(data.message || 'Film récupéré et ajouté aux suggestions !', 'success');
      if (titleInput) titleInput.value = '';
      if (modal) modal.classList.add('hidden');

      loadMovies();
    } catch (err) {
      console.error(err);
      showToast('Erreur de connexion lors de la suggestion.', 'error');
    }
  }

  // ----------------- Snacks & Concession Stand -----------------

  async function loadProducts() {
    try {
      const res = await fetch('/api/products');
      const data = await res.json();
      state.products = data.products || [];
      renderProducts();
    } catch (err) {
      console.error('Failed to load products', err);
      if (elements.snacksGrid) {
        elements.snacksGrid.innerHTML = `<div class="empty-state">Unable to load snacks menu.</div>`;
      }
    }
  }

  function renderProducts() {
    if (!elements.snacksGrid) return;

    const filtered = state.products.filter((p) => {
      if (state.activeCategory === 'all') return true;
      return p.category === state.activeCategory;
    });

    if (filtered.length === 0) {
      elements.snacksGrid.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🍿</div>
          <h3>Aucun produit disponible</h3>
        </div>`;
      return;
    }

    // 1. Définir les tailles de popcorn à regrouper
    const popcornSizes = ['Petit', 'Moyen', 'Grand'];
    
    // 2. Construire les 3 groupes (Petit, Moyen, Grand)
    const groupedPopcorns = popcornSizes.map((size) => {
      const itemsForSize = filtered.filter((p) => p.size === size || p.name.includes(size));
      const prodSucre = itemsForSize.find((p) => p.flavor === 'Sucré' || p.name.toLowerCase().includes('sucré'));
      const prodSale = itemsForSize.find((p) => p.flavor === 'Salé' || p.name.toLowerCase().includes('salé'));
      
      return {
        size: size,
        price: itemsForSize[0] ? itemsForSize[0].price : 0,
        emoji: itemsForSize[0] ? itemsForSize[0].emoji : '🍿',
        sucre: prodSucre,
        sale: prodSale,
      };
    }).filter((g) => g.sucre || g.sale); // Garder uniquement les tailles existantes

    // 3. Produits hors popcorn (boissons, friandises, combos)
    const otherProducts = filtered.filter((p) => p.category !== 'popcorn' && !popcornSizes.some(s => p.name.includes(s)));

    let html = '';

    // Cartes regroupées Popcorn (3 cartes : Petit, Moyen, Grand)
    html += groupedPopcorns.map((group) => `
      <div class="snack-card">
        <div class="snack-header">
          <span class="snack-emoji">${group.emoji || '🍿'}</span>
          <span class="snack-price-tag">€${group.price.toFixed(2)}</span>
        </div>

        <h3 class="snack-name">${escapeHtml(group.size)}</h3>

        <div class="snack-flavor-actions" style="display: flex; gap: 8px; margin-top: 1rem;">
          ${group.sucre ? `<button class="btn btn-secondary btn-add-snack" data-add-id="${group.sucre.id}" style="flex: 1;">+ Sucré</button>` : ''}
          ${group.sale ? `<button class="btn btn-secondary btn-add-snack" data-add-id="${group.sale.id}" style="flex: 1;">+ Salé</button>` : ''}
        </div>
      </div>
    `).join('');

    // Cartes pour les autres produits éventuels
    html += otherProducts.map((prod) => `
      <div class="snack-card" data-product-id="${prod.id}">
        <div class="snack-header">
          <span class="snack-emoji">${prod.emoji || '🍿'}</span>
          <span class="snack-price-tag">€${prod.price.toFixed(2)}</span>
        </div>
        <h3 class="snack-name">${escapeHtml(prod.name)}</h3>
        <button class="btn btn-secondary btn-add-snack" data-add-id="${prod.id}" style="width: 100%; margin-top: 1rem;">
          + Ajouter au panier
        </button>
      </div>
    `).join('');

    elements.snacksGrid.innerHTML = html;

    // Attacher l'événement d'ajout au panier sur tous les boutons
    elements.snacksGrid.querySelectorAll('.btn-add-snack').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const prodId = parseInt(e.currentTarget.dataset.addId, 10);
        addToCart(prodId);
      });
    });
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
        emoji: product.emoji || '🍿',
        quantity: 1,
      });
    }

    saveCart();
    updateCartUI();
    showToast(`Added 1x ${product.name} to your basket!`, 'info');
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

    if (elements.placeOrderBtn) elements.placeOrderBtn.disabled = totalCount === 0;

    if (!elements.cartItemsList) return;

    if (state.cart.length === 0) {
      elements.cartItemsList.innerHTML = `
        <div class="empty-cart-message">
          <span>🍿</span>
          <p>Your snack basket is empty.</p>
        </div>
      `;
    } else {
      elements.cartItemsList.innerHTML = state.cart
        .map(
          (it) => `
        <div class="cart-item-row">
          <div class="cart-item-info">
            <div class="cart-item-title">${it.emoji} ${escapeHtml(it.name)}</div>
            <div class="cart-item-price">€${(it.price * it.quantity).toFixed(2)} (€${it.price.toFixed(2)} ea)</div>
          </div>
          <div class="cart-qty-controls">
            <button class="qty-btn" data-qty-id="${it.product_id}" data-delta="-1">−</button>
            <span class="cart-item-qty">${it.quantity}</span>
            <button class="qty-btn" data-qty-id="${it.product_id}" data-delta="1">+</button>
          </div>
        </div>
      `
        )
        .join('');

      elements.cartItemsList.querySelectorAll('.qty-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const id = parseInt(e.currentTarget.dataset.qtyId, 10);
          const delta = parseInt(e.currentTarget.dataset.delta, 10);
          updateQuantity(id, delta);
        });
      });
    }
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
    const customerName = elements.checkoutNameInput ? elements.checkoutNameInput.value.trim() : '';
    if (!customerName) {
      showToast('Please enter your name for pickup!', 'error');
      if (elements.checkoutNameInput) elements.checkoutNameInput.focus();
      return;
    }

    setUsername(customerName);

    if (state.cart.length === 0) {
      showToast('Your basket is empty.', 'error');
      return;
    }

    if (elements.placeOrderBtn) {
      elements.placeOrderBtn.disabled = true;
      elements.placeOrderBtn.textContent = 'Generating Ticket Pass...';
    }

    try {
      const payload = {
        customer_name: customerName,
        items: state.cart.map((it) => ({
          product_id: it.product_id,
          quantity: it.quantity,
        })),
      };

      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Failed to place order.', 'error');
        if (elements.placeOrderBtn) {
          elements.placeOrderBtn.disabled = false;
          elements.placeOrderBtn.textContent = 'Place Order & Generate Ticket Pass 🎟️';
        }
        return;
      }

      const order = data.order;
      state.myOrders.unshift(order.order_code);
      localStorage.setItem('cinema_my_orders', JSON.stringify(state.myOrders));

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

      if (elements.orderSuccessModal) elements.orderSuccessModal.classList.remove('hidden');
      loadMyOrders();
    } catch (err) {
      console.error(err);
      showToast('Network error while placing order.', 'error');
    } finally {
      if (elements.placeOrderBtn) {
        elements.placeOrderBtn.disabled = false;
        elements.placeOrderBtn.textContent = 'Place Order & Generate Ticket Pass 🎟️';
      }
    }
  }

  // ----------------- My Orders / Passes -----------------

  async function loadMyOrders() {
    const nameFilter = (elements.orderLookupName ? elements.orderLookupName.value.trim() : '') || state.username;

    try {
      let url = '/api/orders';
      if (nameFilter) {
        url += `?customer=${encodeURIComponent(nameFilter)}`;
      }

      const res = await fetch(url);
      const data = await res.json();
      const orders = data.orders || [];

      if (elements.myOrdersBadge) {
        if (orders.length > 0) {
          elements.myOrdersBadge.textContent = orders.length;
          elements.myOrdersBadge.classList.remove('hidden');
        } else {
          elements.myOrdersBadge.classList.add('hidden');
        }
      }

      renderMyOrders(orders);
    } catch (err) {
      console.error(err);
      if (elements.ticketsContainer) {
        elements.ticketsContainer.innerHTML = `<div class="empty-state">Unable to load orders.</div>`;
      }
    }
  }

  function renderMyOrders(orders) {
    if (!elements.ticketsContainer) return;

    if (!orders || orders.length === 0) {
      elements.ticketsContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🍿</div>
          <h3>No Orders Found</h3>
          <p>No snack orders found for this name yet. Grab some popcorn for the movie!</p>
          <button class="btn btn-primary" id="btn-browse-empty">Browse Concession Menu</button>
        </div>
      `;
      const btn = document.getElementById('btn-browse-empty');
      if (btn) btn.addEventListener('click', () => switchTab('snacks-tab'));
      return;
    }

    elements.ticketsContainer.innerHTML = orders
      .map((ord) => {
        let statusClass = 'status-pending';
        let statusText = '🟡 Pending Preparation';
        if (ord.status === 'preparing') {
          statusClass = 'status-preparing';
          statusText = '🟠 Preparing at Counter';
        } else if (ord.status === 'ready') {
          statusClass = 'status-ready';
          statusText = '🟢 Ready for Pickup!';
        } else if (ord.status === 'collected') {
          statusClass = 'status-collected';
          statusText = '⚪ Collected';
        }

        return `
        <div class="ticket-card">
          <div class="ticket-pass-header">
            <div>
              <span class="ticket-label">PASS CODE</span>
              <div class="ticket-pass-code">${escapeHtml(ord.order_code)}</div>
            </div>
            <div style="text-align: right;">
              <span class="status-pill ${statusClass}">${statusText}</span>
              <div style="margin-top: 0.35rem;">
                <span class="payment-pill ${ord.is_paid ? 'payment-paid' : 'payment-unpaid'}">
                  ${ord.is_paid ? '✓ Paid' : 'Due at counter'}
                </span>
              </div>
            </div>
          </div>

          <div style="font-size: 0.85rem; color: #fff; font-weight: 700; margin-bottom: 0.5rem;">
            Customer: ${escapeHtml(ord.customer_name)}
          </div>

          <div class="ticket-items-summary">
            ${(ord.items || [])
              .map(
                (it) => `
              <div class="ticket-item-line">
                <span>${it.quantity}x ${escapeHtml(it.product_name)}</span>
                <span>€${(it.quantity * it.unit_price).toFixed(2)}</span>
              </div>
            `
              )
              .join('')}
          </div>

          <div class="ticket-footer">
            <span>Total Amount</span>
            <span class="ticket-total-price">€${ord.total_price.toFixed(2)}</span>
          </div>
        </div>
      `;
      })
      .join('');
  }

  // ----------------- Letterboxd Reviews -----------------

  function initStarPicker() {
    if (!elements.starPicker) return;

    elements.starPicker.innerHTML = [1, 2, 3, 4, 5]
      .map((val) => `<span class="star-item" data-value="${val}">★</span>`)
      .join('');

    const stars = elements.starPicker.querySelectorAll('.star-item');

    const updateStarsVisual = (rating) => {
      stars.forEach((s) => {
        const val = parseFloat(s.dataset.value);
        if (val <= rating) {
          s.classList.add('selected');
        } else {
          s.classList.remove('selected');
        }
      });
      if (elements.starRatingText) {
        elements.starRatingText.textContent = `${rating.toFixed(1)} / 5.0`;
      }
    };

    stars.forEach((s) => {
      s.addEventListener('click', () => {
        state.currentRating = parseFloat(s.dataset.value);
        updateStarsVisual(state.currentRating);
      });
    });

    updateStarsVisual(state.currentRating);
  }

  async function loadReviews(movieId) {
    if (!movieId) return;
    try {
      const res = await fetch(`/api/reviews?movie_id=${movieId}`);
      const data = await res.json();
      renderReviews(data);
    } catch (err) {
      console.error('Failed to load reviews', err);
    }
  }

  function renderReviews(data) {
    const reviews = data.reviews || [];
    if (elements.reviewsAvgScore) elements.reviewsAvgScore.textContent = (data.avg_score || 0).toFixed(1);
    if (elements.reviewsTotalCount) elements.reviewsTotalCount.textContent = `${reviews.length} reviews`;
    if (elements.feedReviewCount) elements.feedReviewCount.textContent = `${reviews.length} reviews`;

    if (elements.reviewsStarsVisual) {
      const avg = data.avg_score || 0;
      elements.reviewsStarsVisual.textContent = '★'.repeat(Math.round(avg)) + '☆'.repeat(5 - Math.round(avg));
    }

    if (!elements.reviewsFeed) return;

    if (reviews.length === 0) {
      elements.reviewsFeed.innerHTML = `<div class="empty-state">No reviews yet for this movie. Be the first!</div>`;
      return;
    }

    elements.reviewsFeed.innerHTML = reviews
      .map(
        (r) => `
        <div class="review-card">
          <div class="review-header">
            <span class="review-author">${escapeHtml(r.author_name)}</span>
            <span class="review-stars">${'★'.repeat(Math.round(r.rating))}${'☆'.repeat(5 - Math.round(r.rating))} (${r.rating.toFixed(1)})</span>
          </div>
          <p class="review-text">${escapeHtml(r.review_text)}</p>
          <span class="review-date">${new Date(r.created_at || Date.now()).toLocaleDateString()}</span>
        </div>
      `
      )
      .join('');
  }

  async function submitReview() {
    if (!state.selectedReviewMovieId) {
      showToast('Please select a movie first.', 'error');
      return;
    }

    const author = elements.reviewAuthorInput ? elements.reviewAuthorInput.value.trim() : state.username;
    const text = elements.reviewTextInput ? elements.reviewTextInput.value.trim() : '';

    if (!author || !text) {
      showToast('Please enter your name and review text.', 'error');
      return;
    }

    setUsername(author);

    try {
      const res = await fetch('/api/reviews', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          movie_id: parseInt(state.selectedReviewMovieId, 10),
          reviewer_name: author,
          rating: state.currentRating,
          review_text: text,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Failed to submit review.', 'error');
        return;
      }

      showToast('Review submitted successfully!', 'success');
      if (elements.reviewTextInput) elements.reviewTextInput.value = '';
      loadReviews(state.selectedReviewMovieId);
    } catch (err) {
      console.error(err);
      showToast('Error submitting review.', 'error');
    }
  }

  // ----------------- Wooclap Word Cloud -----------------

  async function loadWordCloud(movieId) {
    if (!movieId) return;
    try {
      const res = await fetch(`/api/wordcloud?movie_id=${movieId}`);
      const data = await res.json();
      renderWordCloud(data);
    } catch (err) {
      console.error('Failed to load word cloud', err);
    }
  }

  function renderWordCloud(data) {
    const words = data.words || [];
    if (elements.wordcloudTotalSubmissions) {
      elements.wordcloudTotalSubmissions.textContent = data.total_count || 0;
    }

    if (!elements.wordcloudStage) return;

    if (words.length === 0) {
      elements.wordcloudStage.innerHTML = `<div class="empty-state">No words submitted yet. Add one below!</div>`;
      return;
    }

    const maxCount = Math.max(...words.map((w) => w.count), 1);
    elements.wordcloudStage.innerHTML = words
      .map((w) => {
        const fontSize = Math.max(0.9, (w.count / maxCount) * 2.5).toFixed(2);
        return `<span class="word-tag" style="font-size: ${fontSize}rem; margin: 6px; display: inline-block;">${escapeHtml(w.word)}</span>`;
      })
      .join('');
  }

  async function submitWord() {
    if (!state.selectedWordCloudMovieId) {
      showToast('Please select a movie.', 'error');
      return;
    }

    const word = elements.wordcloudWordInput ? elements.wordcloudWordInput.value.trim() : '';
    if (!word) {
      showToast('Please enter a word.', 'error');
      return;
    }

    try {
      const res = await fetch('/api/wordcloud', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          movie_id: parseInt(state.selectedWordCloudMovieId, 10),
          word: word,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Failed to submit word.', 'error');
        return;
      }

      showToast('Word added to cloud!', 'success');
      if (elements.wordcloudWordInput) elements.wordcloudWordInput.value = '';
      loadWordCloud(state.selectedWordCloudMovieId);
    } catch (err) {
      console.error(err);
      showToast('Error submitting word.', 'error');
    }
  }

  function startWordCloudPolling() {
    stopWordCloudPolling();
    state.wordCloudPollInterval = setInterval(() => {
      if (state.selectedWordCloudMovieId) {
        loadWordCloud(state.selectedWordCloudMovieId);
      }
    }, 5000);
  }

  function stopWordCloudPolling() {
    if (state.wordCloudPollInterval) {
      clearInterval(state.wordCloudPollInterval);
      state.wordCloudPollInterval = null;
    }
  }

  // ----------------- Admin Panel -----------------

  async function handleAdminLogin() {
    const pin = elements.adminPinInput ? elements.adminPinInput.value.trim() : '';
    if (!pin) {
      showToast('Please enter the admin PIN.', 'error');
      return;
    }
    await verifyAdminPin(pin);
  }

  async function verifyAdminPin(pin) {
    try {
      const res = await fetch('/api/admin/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pin }),
      });

      if (!res.ok) {
        showToast('Invalid Admin PIN', 'error');
        handleAdminLogout();
        return;
      }

      state.adminPin = pin;
      sessionStorage.setItem('cinema_admin_pin', pin);

      if (elements.adminLockScreen) elements.adminLockScreen.classList.add('hidden');
      if (elements.adminDashboard) elements.adminDashboard.classList.remove('hidden');

      loadAdminDashboardData();
      startAdminPolling();
    } catch (err) {
      console.error(err);
      showToast('Admin verification failed.', 'error');
    }
  }

  function handleAdminLogout() {
    state.adminPin = null;
    sessionStorage.removeItem('cinema_admin_pin');
    stopAdminPolling();

    if (elements.adminLockScreen) elements.adminLockScreen.classList.remove('hidden');
    if (elements.adminDashboard) elements.adminDashboard.classList.add('hidden');
    if (elements.adminPinInput) elements.adminPinInput.value = '';
  }

  async function loadAdminDashboardData() {
    if (!state.adminPin) return;

    try {
      const res = await fetch(`/api/admin/dashboard?pin=${encodeURIComponent(state.adminPin)}`);
      if (!res.ok) {
        handleAdminLogout();
        return;
      }

      const data = await res.json();

      if (elements.kpiAttendees) elements.kpiAttendees.textContent = data.total_attendees || 0;
      if (elements.kpiVotes) elements.kpiVotes.textContent = data.total_votes || 0;
      if (elements.kpiOrders) elements.kpiOrders.textContent = data.total_orders || 0;
      if (elements.kpiPendingOrders) elements.kpiPendingOrders.textContent = data.pending_orders || 0;
      if (elements.kpiRevenue) elements.kpiRevenue.textContent = `€${(data.total_revenue || 0).toFixed(2)}`;
      if (elements.kpiPaidRevenue) elements.kpiPaidRevenue.textContent = `€${(data.paid_revenue || 0).toFixed(2)}`;

      state.adminOrdersCache = data.orders || [];
      renderAdminOrdersTable(state.adminOrdersCache);

      if (elements.topSnacksList && data.top_snacks) {
        elements.topSnacksList.innerHTML = data.top_snacks
          .map((s) => `<li>${escapeHtml(s.name)}: ${s.quantity_sold} sold</li>`)
          .join('');
      }
    } catch (err) {
      console.error('Failed to load admin dashboard', err);
    }
  }

  function startAdminPolling() {
    stopAdminPolling();
    state.adminPollInterval = setInterval(loadAdminDashboardData, 4000);
  }

  function stopAdminPolling() {
    if (state.adminPollInterval) {
      clearInterval(state.adminPollInterval);
      state.adminPollInterval = null;
    }
  }

  function renderAdminOrdersTable(orders) {
    if (!elements.adminOrdersTbody) return;

    const filter = elements.adminOrderFilter ? elements.adminOrderFilter.value : 'all';
    const filtered = orders.filter((o) => {
      if (filter === 'all') return true;
      if (filter === 'pending') return o.status === 'pending' || o.status === 'preparing';
      if (filter === 'ready') return o.status === 'ready';
      if (filter === 'collected') return o.status === 'collected';
      return true;
    });

    if (filtered.length === 0) {
      elements.adminOrdersTbody.innerHTML = `<tr><td colspan="6" class="text-center">No orders match filter.</td></tr>`;
      return;
    }

    elements.adminOrdersTbody.innerHTML = filtered
      .map(
        (o) => `
        <tr>
          <td><strong>${escapeHtml(o.order_code)}</strong></td>
          <td>${escapeHtml(o.customer_name)}</td>
          <td>${(o.items || []).map((i) => `${i.quantity}x ${escapeHtml(i.product_name)}`).join(', ')}</td>
          <td>€${o.total_price.toFixed(2)}</td>
          <td>
            <select class="order-status-select" data-order-id="${o.id}">
              <option value="pending" ${o.status === 'pending' ? 'selected' : ''}>Pending</option>
              <option value="preparing" ${o.status === 'preparing' ? 'selected' : ''}>Preparing</option>
              <option value="ready" ${o.status === 'ready' ? 'selected' : ''}>Ready</option>
              <option value="collected" ${o.status === 'collected' ? 'selected' : ''}>Collected</option>
            </select>
          </td>
          <td>
            <button class="btn btn-sm ${o.is_paid ? 'btn-success' : 'btn-outline'}" data-pay-id="${o.id}">
              ${o.is_paid ? '✓ Paid' : 'Mark Paid'}
            </button>
          </td>
        </tr>
      `
      )
      .join('');

    elements.adminOrdersTbody.querySelectorAll('.order-status-select').forEach((sel) => {
      sel.addEventListener('change', async (e) => {
        const orderId = e.target.dataset.orderId;
        const newStatus = e.target.value;
        await updateOrderStatus(orderId, newStatus);
      });
    });

    elements.adminOrdersTbody.querySelectorAll('[data-pay-id]').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        const orderId = e.currentTarget.dataset.payId;
        await toggleOrderPaid(orderId);
      });
    });
  }

  async function updateOrderStatus(orderId, status) {
    try {
      const res = await fetch(`/api/admin/orders/${orderId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: state.adminPin, status: status }),
      });
      if (res.ok) {
        showToast('Order status updated', 'success');
        loadAdminDashboardData();
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function toggleOrderPaid(orderId) {
    try {
      const res = await fetch(`/api/admin/orders/${orderId}/pay`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: state.adminPin }),
      });
      if (res.ok) {
        showToast('Payment status updated', 'success');
        loadAdminDashboardData();
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleAddMovie(e) {
    e.preventDefault();
    const formData = new FormData(elements.addMovieForm);
    const movieData = {
      pin: state.adminPin,
      title: formData.get('title'),
      synopsis: formData.get('synopsis'),
      poster_url: formData.get('poster_url'),
      genre: formData.get('genre'),
      runtime: formData.get('runtime'),
      year: parseInt(formData.get('year') || '2026', 10),
    };

    try {
      const res = await fetch('/api/admin/movies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(movieData),
      });

      if (res.ok) {
        showToast('Movie added successfully!', 'success');
        elements.addMovieForm.reset();
        loadMovies();
      } else {
        const data = await res.json();
        showToast(data.error || 'Failed to add movie.', 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Error adding movie.', 'error');
    }
  }

  async function handleResetEvent() {
    if (!confirm('Are you sure you want to reset all votes and orders? This cannot be undone.')) return;

    try {
      const res = await fetch('/api/admin/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: state.adminPin }),
      });

      if (res.ok) {
        showToast('Event data reset successfully.', 'success');
        loadAdminDashboardData();
        loadMovies();
      }
    } catch (err) {
      console.error(err);
      showToast('Error resetting event.', 'error');
    }
  }

  // ----------------- Entry Point -----------------

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();