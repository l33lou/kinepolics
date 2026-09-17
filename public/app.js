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
    cart: JSON.parse(localStorage.getItem('cinema_cart') || '[]'),
    myOrders: JSON.parse(localStorage.getItem('cinema_my_orders') || '[]'),
    activeGenre: 'all',
    movies: [],
    products: [],
    selectedTmdbMovie: null,
    searchDebounceTimer: null,
  };

  // DOM Elements
  const elements = {
    navLinks: document.querySelectorAll('.nav-link, .film-frame'),
    tabPanes: document.querySelectorAll('.tab-pane, .tab-content, section[id]'),
    loginBtn: document.getElementById('loginBtn'),
    userDisplayName: document.getElementById('user-display-name') || document.querySelector('#loginBtn span'),

    // Suggestions / Movies
    moviesGrid: document.getElementById('movies-grid') || document.querySelector('.movie-grid'),
    genreFilters: document.getElementById('genre-filters'),

    // Snacks & Cart
    snacksGrid: document.getElementById('snacks-grid') || document.querySelector('.snack-grid'),
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

    // History Container
    historyList: document.getElementById('history-list'),

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

  function init() {
    setupEventListeners();
    updateUserDisplay();
    updateCartUI();
    loadMovies();
    loadProducts();
    loadHistory();
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
  }

  // ----------------- TMDB Search Integration -----------------

  async function fetchTmdbCandidates(query) {
    const dropdown = document.getElementById('suggest-results-dropdown');
    if (!dropdown) return;

    try {
      const res = await fetch(`/api/tmdb/search?query=${encodeURIComponent(query)}`);
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

    const payload = {
      title: state.selectedTmdbMovie.title,
      year: state.selectedTmdbMovie.year,
      synopsis: state.selectedTmdbMovie.synopsis,
      poster_url: state.selectedTmdbMovie.poster_url,
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

      showToast(data.message || 'Film ajouté aux suggestions !', 'success');
      resetSuggestPreview();
      document.getElementById('suggest-title-input').value = '';
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

  // ----------------- User Identity -----------------

  function updateUserDisplay() {
    const displayName = state.username || 'Se connecter';
    if (elements.userDisplayName) elements.userDisplayName.textContent = displayName;
    if (elements.loginBtn) {
      const span = elements.loginBtn.querySelector('span');
      if (span) span.textContent = displayName;
    }
    if (state.username && elements.checkoutNameInput) {
      elements.checkoutNameInput.value = state.username;
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
      const res = await fetch('/api/movies');
      const data = await res.json();
      state.movies = data.movies || [];
      renderMovies();
    } catch (err) {
      console.error('Failed to load movies', err);
      if (elements.moviesGrid) {
        elements.moviesGrid.innerHTML = `<div class="empty-state">Failed to load suggestions. Server error.</div>`;
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
      .map(
        (m) => `
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
              ${m.suggested_by ? `<span class="badge-suggested-by">💡 Proposé par ${escapeHtml(m.suggested_by)}</span>` : ''}
            </div>

            <p class="movie-desc">${escapeHtml(m.synopsis || 'Aucun synopsis disponible.')}</p>
          </div>
        </div>
      `
      )
      .join('');
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

    const popcornSizes = ['Petit', 'Moyen', 'Grand'];
    
    const groupedPopcorns = popcornSizes.map((size) => {
      const itemsForSize = state.products.filter((p) => p.size === size || p.name.includes(size));
      const prodSucre = itemsForSize.find((p) => p.flavor === 'Sucré' || p.name.toLowerCase().includes('sucré'));
      const prodSale = itemsForSize.find((p) => p.flavor === 'Salé' || p.name.toLowerCase().includes('salé'));
      
      return {
        size: size,
        price: itemsForSize[0] ? itemsForSize[0].price : 0,
        emoji: itemsForSize[0] ? itemsForSize[0].emoji : '🍿',
        sucre: prodSucre,
        sale: prodSale,
      };
    }).filter((g) => g.sucre || g.sale);

    const otherProducts = state.products.filter((p) => p.category !== 'popcorn' && !popcornSizes.some(s => p.name.includes(s)));

    let html = '';

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

  // ----------------- Historique des Projections -----------------

  function loadHistory() {
    const container = elements.historyList;
    if (!container) return;

    const historicalProjections = [
      { title: "Parasite", date: "03/10/25", rating: 4.8, words: ["Plot twist", "Caillou", "Grandissime", "Sympa", "Absolute cinéma", "Pic à brochette", "Disons"] },
      { title: "Dead Poets Society", date: "10/10/25", rating: 4.9, words: ["Nuwanda", "Carpe diem", "Seize the day boys", "Captain my captain", "Triste", "Old school"] },
      { title: "Isle of dogs", date: "15/10/25", rating: 4.3, words: ["Ouaf ouaf", "Wes Anderson", "Leelou impératrice", "Vive les chiens", "Mr Fox", "Ahouuuu"] },
      { title: "Whiplash", date: "Session Batteur", rating: 5.0, words: ["NOT MY FUCKING TEMPO", "You cock sucker", "FASTER PAUL", "Boum boum", "Sang"] },
      { title: "Hunger games", date: "21/11/25", rating: 4.7, words: ["J'ai faim", "Vive le BDA", "Sanglant", "Le 2", "Trop cool", "Bon appétit Arthur"] },
      { title: "Azur et Asmar", date: "Projection Spéciale", rating: 4.6, words: ["Égalité", "Solidarité", "Choukran", "Excellent film d'animation", "In Shaa Allah"] },
      { title: "Blade Runner 2049", date: "Projection Spéciale", rating: 4.5, words: ["PIERRE MAGRE", "Contre-plongée", "Troublant", "Parfait", "Incompréhensible"] },
      { title: "Mickey 17", date: "Projection Spéciale", rating: 4.1, words: ["Rocambolesque", "Robert Pattinson quel bg", "Gore", "Disney/20", "Plagiat de Nausicaa"] },
      { title: "Frankenstein", date: "2025", rating: 4.2, words: ["C'était très beau", "Smash l'aveugle", "Gore", "Zombie/20", "Créature", "Jacob"] },
      { title: "Le Roi et l'oiseau", date: "Projection Spéciale", rating: 4.4, words: ["Magnifiques costumes", "Liberté", "Travail", "Référence"] },
      { title: "The Cube", date: "Projection Spéciale", rating: 3.9, words: ["Mathématicienne", "Autiste", "Coop", "Martin", "Adèle", "Fin décevante"] },
      { title: "Don't Look Up", date: "Projection Spéciale", rating: 4.0, words: ["Prime", "Téléphone", "J'ai pas compris"] },
      { title: "RRRrrr !!!", date: "20/03/26", rating: 4.7, words: ["Pierre", "Cheveux", "Tg", "Ta gueule", "Fais tout noir", "Les cheuveux"] }
    ];

    container.innerHTML = historicalProjections.map(item => {
      const starsFull = Math.round(item.rating);
      const starsStr = '★'.repeat(starsFull) + '☆'.repeat(5 - starsFull);

      return `
        <div class="history-card">
          <div class="history-header">
            <h3 class="history-movie-title">${escapeHtml(item.title)}</h3>
            <span class="history-date">Séance du ${escapeHtml(item.date)}</span>
          </div>

          <div class="history-rating-row">
            <span class="history-stars">${starsStr}</span>
            <span class="history-score-num">${item.rating.toFixed(1)} / 5.0 (Letterboxd)</span>
          </div>

          <div class="history-wordcloud-box">
            <div class="history-wordcloud-title">💬 Nuage de mots Wooclap de la communauté</div>
            <div class="wordcloud-tags-container">
              ${item.words.map(w => `<span class="history-word-tag">${escapeHtml(w)}</span>`).join('')}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // ----------------- Entry Point -----------------

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();