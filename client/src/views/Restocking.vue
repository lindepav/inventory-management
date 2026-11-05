<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="budget-row">
        <label for="budget-slider" class="budget-label">{{ t('restocking.budgetSlider') }}</label>
        <span class="budget-value">{{ formatCurrency(budget) }}</span>
      </div>
      <input
        id="budget-slider"
        v-model.number="budget"
        type="range"
        min="0"
        :max="MAX_BUDGET"
        step="500"
        class="budget-slider"
        :style="{ '--fill': (budget / MAX_BUDGET * 100) + '%' }"
      />
      <div class="budget-scale">
        <span>{{ formatCurrency(0) }}</span>
        <span>{{ formatCurrency(MAX_BUDGET) }}</span>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card info">
        <div class="stat-label">{{ t('restocking.budget') }}</div>
        <div class="stat-value">{{ formatCurrency(budget) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">{{ t('restocking.selectedTotal') }}</div>
        <div class="stat-value">{{ formatCurrency(selectedTotal) }}</div>
      </div>
      <div :class="['stat-card', remaining < 0 ? 'danger' : 'success']">
        <div class="stat-label">{{ t('restocking.remaining') }}</div>
        <div class="stat-value">{{ formatCurrency(remaining) }}</div>
      </div>
    </div>

    <div v-if="successMessage" class="success-message">{{ successMessage }}</div>
    <div v-if="orderError" class="error">{{ orderError }}</div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="card">
      <div class="card-header">
        <h3 class="card-title">{{ t('restocking.recommendations') }} ({{ rows.length }})</h3>
        <div class="order-actions">
          <span v-if="validationMessage" class="validation">{{ validationMessage }}</span>
          <button class="place-order" :disabled="!canSubmit" @click="placeOrder">
            {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>
      </div>

      <div v-if="rows.length === 0" class="empty">{{ t('restocking.empty') }}</div>
      <div v-else class="table-container">
        <table>
          <thead>
            <tr>
              <th>{{ t('restocking.table.select') }}</th>
              <th>{{ t('restocking.table.item') }}</th>
              <th>{{ t('restocking.table.trend') }}</th>
              <th>{{ t('restocking.table.currentStock') }}</th>
              <th>{{ t('restocking.table.forecastedDemand') }}</th>
              <th>{{ t('restocking.table.shortfall') }}</th>
              <th>{{ t('restocking.table.unitCost') }}</th>
              <th>{{ t('restocking.table.quantity') }}</th>
              <th>{{ t('restocking.table.lineCost') }}</th>
              <th>{{ t('restocking.table.leadTime') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.sku" :class="{ unselected: !row.selected }">
              <td>
                <input v-model="row.selected" type="checkbox" :aria-label="row.sku" />
              </td>
              <td>
                <strong>{{ row.sku }}</strong>
                <div class="item-name">{{ row.name }}</div>
              </td>
              <td>
                <span :class="['badge', row.trend]">{{ t(`trends.${row.trend}`) }}</span>
              </td>
              <td>{{ row.current_stock }}</td>
              <td>{{ row.forecasted_demand }}</td>
              <td><strong>{{ row.shortfall }}</strong></td>
              <td>{{ formatCurrency(row.unit_cost) }}</td>
              <td>
                <input
                  v-model.number="row.quantity"
                  type="number"
                  min="1"
                  :max="row.shortfall"
                  step="1"
                  :class="['qty-input', { invalid: !isQtyValid(row) }]"
                  :disabled="!row.selected"
                />
              </td>
              <td>{{ formatCurrency(lineCost(row)) }}</td>
              <td>{{ row.lead_time_days }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale } = useI18n()

    const MAX_BUDGET = 50000
    const budget = ref(10000)
    const rows = ref([])
    const loading = ref(true)
    const error = ref(null)
    const submitting = ref(false)
    const orderError = ref(null)
    const successMessage = ref(null)

    const formatCurrency = (value) => {
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return Number(value || 0).toLocaleString(locale, {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 2
      })
    }

    const formatDate = (value) => {
      const d = new Date(value)
      if (isNaN(d.getTime())) return value
      return d.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric'
      })
    }

    // Local editable state is rebuilt from server data on every reload
    const loadRecommendations = async () => {
      // Capture requested budget so a stale response cannot overwrite a newer one
      const requested = budget.value
      try {
        loading.value = rows.value.length === 0
        error.value = null
        const data = await api.getRestockRecommendations(requested)
        if (requested !== budget.value) return
        rows.value = data.map(rec => ({
          ...rec,
          selected: true,
          quantity: rec.recommended_qty
        }))
      } catch (err) {
        if (requested !== budget.value) return
        error.value = t('restocking.loadFailed') + ': ' + (err.response?.data?.detail || err.message)
        rows.value = []
      } finally {
        loading.value = false
      }
    }

    let debounceTimer = null
    watch(budget, () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(loadRecommendations, 300)
    })

    const isQtyValid = (row) =>
      Number.isInteger(row.quantity) && row.quantity >= 1 && row.quantity <= row.shortfall

    const lineCost = (row) => {
      const qty = Number.isFinite(row.quantity) ? row.quantity : 0
      return Math.round(qty * row.unit_cost * 100) / 100
    }

    const selectedRows = computed(() => rows.value.filter(r => r.selected))
    const selectedTotal = computed(() =>
      Math.round(selectedRows.value.reduce((sum, r) => sum + lineCost(r), 0) * 100) / 100
    )
    const remaining = computed(() => Math.round((budget.value - selectedTotal.value) * 100) / 100)

    const validationMessage = computed(() => {
      if (selectedRows.value.length === 0) return ''
      if (selectedRows.value.some(r => !isQtyValid(r))) return t('restocking.invalidQty')
      if (selectedTotal.value > budget.value) return t('restocking.overBudget')
      return ''
    })

    const canSubmit = computed(() =>
      !submitting.value &&
      selectedRows.value.length > 0 &&
      !validationMessage.value
    )

    const placeOrder = async () => {
      if (!canSubmit.value) return
      submitting.value = true
      orderError.value = null
      successMessage.value = null
      try {
        const order = await api.placeRestockOrder({
          items: selectedRows.value.map(r => ({ sku: r.sku, quantity: r.quantity })),
          budget: budget.value
        })
        successMessage.value = t('restocking.success', {
          orderNumber: order.order_number,
          days: order.lead_time_days,
          date: formatDate(order.expected_delivery)
        })
        await loadRecommendations()
      } catch (err) {
        orderError.value = err.response?.data?.detail || t('restocking.orderFailed')
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)
    onBeforeUnmount(() => clearTimeout(debounceTimer))

    return {
      t,
      MAX_BUDGET,
      budget,
      rows,
      loading,
      error,
      submitting,
      orderError,
      successMessage,
      selectedTotal,
      remaining,
      validationMessage,
      canSubmit,
      formatCurrency,
      isQtyValid,
      lineCost,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 1rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 24px;
  background: transparent;
  cursor: pointer;
}

.budget-slider::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(to right, #2563eb var(--fill), #e2e8f0 var(--fill));
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  margin-top: -7px;
  border-radius: 50%;
  background: white;
  border: 2px solid #2563eb;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.2);
}

.budget-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
}

.budget-slider::-moz-range-progress {
  height: 6px;
  border-radius: 3px;
  background: #2563eb;
}

.budget-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  border: 2px solid #2563eb;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.2);
}

.budget-slider:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 4px;
  border-radius: 4px;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.success-message {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #166534;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  font-size: 0.938rem;
}

.order-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.validation {
  font-size: 0.813rem;
  color: #991b1b;
}

.place-order {
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.25rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.place-order:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order:disabled {
  background: #cbd5e1;
  color: #64748b;
  cursor: not-allowed;
}

.empty {
  text-align: center;
  padding: 3rem;
  color: #64748b;
  font-size: 0.938rem;
}

.item-name {
  font-size: 0.813rem;
  color: #64748b;
}

tr.unselected td {
  color: #94a3b8;
}

.qty-input {
  width: 80px;
  padding: 0.375rem 0.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #0f172a;
}

.qty-input:focus {
  outline: none;
  border-color: #2563eb;
}

.qty-input.invalid {
  border-color: #dc2626;
  background: #fef2f2;
}

.qty-input:disabled {
  background: #f8fafc;
  color: #94a3b8;
}
</style>
