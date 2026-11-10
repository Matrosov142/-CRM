import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';

const API = import.meta.env.VITE_API_URL || '';

function csrfHeaders(): Record<string,string> {
  const match = document.cookie.match(/(?:^|; )potok_csrf=([^;]+)/);
  return match ? {'X-CSRF-Token': decodeURIComponent(match[1])} : {};
}

type Company = { id: string; name: string; status: string };
type CurrentUser = { id: string; email: string; company_id: string; role: string };
type DashboardSummary = { open_tenders: number; authorized_procurement_orders: number; pending_approvals: number; active_reservations: number };

const ROLE_LABELS: Record<string,string> = {
  director:'Директор', tender_specialist:'Специалист тендерного отдела',
  procurement_manager:'Менеджер закупок', warehouse:'Склад', logistics:'Логист', accounting:'Бухгалтер',
};
type DeliveryOption = { method: string; name: string; total: string; delivery_days?: number | null; source: string; breakdown?: Record<string,string> };
type DeliveryHistory = { id:string; origin:string; destination:string; distance_km_one_way:string; cargo_description:string; options:DeliveryOption[]; selected_option_index:number|null; created_at:string };

export default function App() {
  const [mode, setMode] = useState<'login'|'register'>('login');
  const [companyName, setCompanyName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  // Access token is memory-only; never persist bearer credentials in browser storage.
  const [token, setToken] = useState('cookie-session');
  const [company, setCompany] = useState<Company | null>(null);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [loadingCompany, setLoadingCompany] = useState(false);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [dashboardBusy, setDashboardBusy] = useState(false);
  const [dashboardMessage, setDashboardMessage] = useState('');
  const [section, setSection] = useState<'home'|'tenders'|'delivery'|'shipments'|'security'>('home');
  const [tenders, setTenders] = useState<any[]>([]);
  const [tenderBusy, setTenderBusy] = useState(false);
  const [tenderMessage, setTenderMessage] = useState('');
  const [selectedTender, setSelectedTender] = useState<any|null>(null);
  const [tenderPositions, setTenderPositions] = useState<any[]>([]);
  const [positionForm, setPositionForm] = useState({item_name:'', specification:'', quantity:'1', unit:'шт.', estimated_unit_price:'', notes:''});
  const [positionBusy, setPositionBusy] = useState(false);
  const [pricingPosition, setPricingPosition] = useState<any|null>(null);
  const [pricingBusy, setPricingBusy] = useState(false);
  const [pricingPreview, setPricingPreview] = useState<any|null>(null);
  const [pricingVersions, setPricingVersions] = useState<any[]>([]);
  const [pricingSaveBusy, setPricingSaveBusy] = useState(false);
  const [pricingForm, setPricingForm] = useState({purchase:'', logistics:'0', processing:'0', packaging:'0', tax:'0', other:'0', conservative_margin:'10', target_margin:'20', aggressive_margin:'30'});
  const [tenderForm, setTenderForm] = useState({platform:'B2B-Center', tender_number:'', customer_name:'', subject:'', initial_price:'', deadline:'', delivery_region:'', prospectivity:'medium', notes:''});
  const [browserSessions, setBrowserSessions] = useState<any[]>([]);
  const [sessionsBusy, setSessionsBusy] = useState(false);
  const [shipments, setShipments] = useState<any[]>([]);
  const [actualCosts, setActualCosts] = useState<Record<string,string>>({});
  const [shipmentBusy, setShipmentBusy] = useState(false);
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [distance, setDistance] = useState('100');
  const [cargo, setCargo] = useState('');
  const [fuelUse, setFuelUse] = useState('20');
  const [fuelPrice, setFuelPrice] = useState('60');
  const [driverCost, setDriverCost] = useState('0');
  const [depreciation, setDepreciation] = useState('0');
  const [maintenance, setMaintenance] = useState('0');
  const [carrierName, setCarrierName] = useState('');
  const [carrierQuote, setCarrierQuote] = useState('');
  const [deliveryBusy, setDeliveryBusy] = useState(false);
  const [deliveryMessage, setDeliveryMessage] = useState('');
  const [deliveryOptions, setDeliveryOptions] = useState<DeliveryOption[]>([]);
  const [deliveryEstimateId, setDeliveryEstimateId] = useState('');
  const [deliveryHistory, setDeliveryHistory] = useState<DeliveryHistory[]>([]);
  const [selectedDeliveryIndex, setSelectedDeliveryIndex] = useState<number|null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    if (!token) { setCompany(null); return; }
    let cancelled = false;
    setLoadingCompany(true);
    fetch(`${API}/api/v1/companies/current`, {
      credentials: 'include'
    }).then(async r => {
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Не удалось загрузить компанию');
      if (!cancelled) setCompany(data);
    }).catch(err => {
      if (!cancelled) {
        setMessage(err instanceof Error ? err.message : 'Ошибка соединения');
        setToken('');
      }
    }).finally(() => { if (!cancelled) setLoadingCompany(false); });
    return () => { cancelled = true; };
  }, [token]);

  useEffect(() => {
    if (!token) { setCurrentUser(null); return; }
    let cancelled = false;
    fetch(`${API}/api/v1/users/me`, {credentials:'include'})
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить профиль');
        if (!cancelled) setCurrentUser(data);
      })
      .catch(() => { if (!cancelled) setCurrentUser(null); });
    return () => { cancelled = true; };
  }, [token]);

  async function loadDashboard() {
    if (!token) return;
    setDashboardBusy(true);
    setDashboardMessage('');
    try {
      const response = await fetch(`${API}/api/v1/dashboard/summary`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить показатели компании');
      setDashboardSummary(data);
    } catch (err) {
      setDashboardMessage(err instanceof Error ? err.message : 'Ошибка загрузки показателей');
      setDashboardSummary(null);
    } finally { setDashboardBusy(false); }
  }

  useEffect(() => {
    if (!token || !company) { setDashboardSummary(null); return; }
    void loadDashboard();
  }, [token, company]);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setMessage('');
    try {
      const endpoint = mode === 'register' ? '/api/v1/auth/session/register-company' : '/api/v1/auth/session/login';
      const body = mode === 'register'
        ? { company_name: companyName, email, password }
        : { email, password };
      const response = await fetch(`${API}${endpoint}`, {
        method: 'POST', credentials: 'include', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось выполнить запрос');
      setToken('cookie-session');
      setMessage('Авторизация выполнена.');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Ошибка соединения с сервером');
    } finally { setBusy(false); }
  }

  async function calculateDelivery(e: FormEvent) {
    e.preventDefault(); setDeliveryBusy(true); setDeliveryMessage(''); setDeliveryOptions([]); setSelectedDeliveryIndex(null);
    try {
      const carrier_options = carrierName.trim() && carrierQuote.trim()
        ? [{ company_name: carrierName.trim(), quoted_total: carrierQuote.trim() }] : [];
      const payload: any = {
        origin, destination, distance_km_one_way: distance, cargo_description: cargo,
        carrier_options,
        own_fleet: { fuel_consumption_l_100km: fuelUse, fuel_price_per_l: fuelPrice,
          driver_cost: driverCost, depreciation_per_km: depreciation,
          maintenance_per_km: maintenance, round_trip: true }
      };
      const response = await fetch(`${API}/api/v1/transport/estimate`, {
        method: 'POST', credentials: 'include', headers: {'Content-Type':'application/json', ...csrfHeaders()},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось рассчитать доставку');
      setDeliveryEstimateId(data.id);
      setDeliveryOptions(data.options || []);
      setDeliveryMessage(data.notice || 'Расчёт выполнен.');
    } catch (err) {
      setDeliveryMessage(err instanceof Error ? err.message : 'Ошибка соединения с сервером');
    } finally { setDeliveryBusy(false); }
  }

  async function loadTenders() {
    setTenderBusy(true); setTenderMessage('');
    try {
      const response = await fetch(`${API}/api/v1/tenders`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить тендеры');
      setTenders(Array.isArray(data) ? data : []);
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка загрузки тендеров'); }
    finally { setTenderBusy(false); }
  }

  async function openTenderPositions(tender:any) {
    setSelectedTender(tender); setTenderPositions([]); setTenderMessage('');
    try {
      const response = await fetch(`${API}/api/v1/tenders/${tender.id}/positions`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить позиции');
      setTenderPositions(Array.isArray(data) ? data : []);
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка загрузки позиций'); }
  }

  async function createTenderPosition(e: FormEvent) {
    e.preventDefault(); if (!selectedTender) return;
    setPositionBusy(true); setTenderMessage('');
    try {
      const payload:any = {...positionForm};
      if (!payload.estimated_unit_price) delete payload.estimated_unit_price;
      const response = await fetch(`${API}/api/v1/tenders/${selectedTender.id}/positions`, {
        method:'POST', credentials:'include', headers:{'Content-Type':'application/json', ...csrfHeaders()}, body:JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось добавить позицию');
      setTenderPositions(v=>[...v,data]);
      setPositionForm({item_name:'', specification:'', quantity:'1', unit:'шт.', estimated_unit_price:'', notes:''});
      setTenderMessage('Позиция добавлена. Проверьте характеристики и цену.');
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка добавления позиции'); }
    finally { setPositionBusy(false); }
  }

  async function calculatePositionPricing(e: FormEvent) {
    e.preventDefault(); if (!selectedTender || !pricingPosition) return;
    setPricingBusy(true); setTenderMessage(''); setPricingPreview(null);
    try {
      const response = await fetch(`${API}/api/v1/tenders/${selectedTender.id}/positions/${pricingPosition.id}/pricing-preview`, {
        method:'POST', credentials:'include', headers:{'Content-Type':'application/json', ...csrfHeaders()}, body:JSON.stringify(pricingForm)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось рассчитать себестоимость');
      setPricingPreview(data);
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка расчёта'); }
    finally { setPricingBusy(false); }
  }

  async function loadPricingVersions(positionId:string) {
    if (!selectedTender) return;
    try {
      const response = await fetch(`${API}/api/v1/tenders/${selectedTender.id}/positions/${positionId}/pricing-calculations`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить историю расчётов');
      setPricingVersions(Array.isArray(data) ? data : []);
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка загрузки истории расчётов'); }
  }

  async function savePositionPricing() {
    if (!selectedTender || !pricingPosition || !pricingPreview) return;
    setPricingSaveBusy(true); setTenderMessage('');
    try {
      const response = await fetch(`${API}/api/v1/tenders/${selectedTender.id}/positions/${pricingPosition.id}/pricing-calculations`, {
        method:'POST', credentials:'include', headers:{'Content-Type':'application/json', ...csrfHeaders()}, body:JSON.stringify(pricingForm)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить версию расчёта');
      await loadPricingVersions(pricingPosition.id);
      setTenderMessage(`Расчёт сохранён как версия №${data.version}.`);
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка сохранения расчёта'); }
    finally { setPricingSaveBusy(false); }
  }

  async function createTender(e: FormEvent) {
    e.preventDefault(); setTenderBusy(true); setTenderMessage('');
    try {
      const payload = {...tenderForm, initial_price:tenderForm.initial_price, deadline:new Date(tenderForm.deadline).toISOString()};
      const response = await fetch(`${API}/api/v1/tenders`, {method:'POST', credentials:'include', headers:{'Content-Type':'application/json', ...csrfHeaders()}, body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось создать тендер');
      setTenderMessage(`Тендер ${data.tender_number} создан.`);
      setTenderForm(v=>({...v,tender_number:'',customer_name:'',subject:'',initial_price:'',deadline:'',delivery_region:'',notes:''}));
      await loadTenders();
    } catch (err) { setTenderMessage(err instanceof Error ? err.message : 'Ошибка создания тендера'); }
    finally { setTenderBusy(false); }
  }

  async function loadShipments() {
    setShipmentBusy(true);
    try {
      const response = await fetch(`${API}/api/v1/warehouse/shipments`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить отгрузки');
      setShipments(data);
    } catch (err) { setDeliveryMessage(err instanceof Error ? err.message : 'Ошибка загрузки отгрузок'); }
    finally { setShipmentBusy(false); }
  }

  async function saveActualCost(shipmentId:string) {
    const raw = actualCosts[shipmentId];
    if (raw === undefined || raw.trim() === '' || !Number.isFinite(Number(raw)) || Number(raw) < 0) {
      setDeliveryMessage('Введите фактическую стоимость не меньше нуля.'); return;
    }
    try {
      const response = await fetch(`${API}/api/v1/warehouse/shipments/${shipmentId}/actual-delivery-cost`, {
        method:'POST', credentials:'include', headers:{'Content-Type':'application/json', ...csrfHeaders()},
        body:JSON.stringify({actual_cost:raw, note:'Внесено из интерфейса отгрузок'})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить фактическую стоимость');
      setDeliveryMessage(`Фактическая стоимость сохранена. Отклонение от плана: ${data.variance ?? '—'} ₽.`);
      await loadShipments();
    } catch (err) { setDeliveryMessage(err instanceof Error ? err.message : 'Ошибка сохранения'); }
  }

  async function loadDeliveryHistory() {
    try {
      const response = await fetch(`${API}/api/v1/transport/estimates`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить историю');
      setDeliveryHistory(data); setHistoryOpen(true);
    } catch (err) { setDeliveryMessage(err instanceof Error ? err.message : 'Ошибка загрузки истории'); }
  }

  async function chooseDeliveryOption(index:number) {
    if (!deliveryEstimateId) return;
    try {
      const response = await fetch(`${API}/api/v1/transport/estimates/${deliveryEstimateId}/select?option_index=${index}`, {
        method:'POST', credentials:'include', headers:csrfHeaders()
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось сохранить выбор');
      setSelectedDeliveryIndex(index); setDeliveryMessage(data.message);
    } catch (err) { setDeliveryMessage(err instanceof Error ? err.message : 'Ошибка сохранения выбора'); }
  }


  async function loadBrowserSessions() {
    setSessionsBusy(true);
    try {
      const response = await fetch(`${API}/api/v1/auth/session/sessions`, {credentials:'include'});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось загрузить сеансы');
      setBrowserSessions(data.sessions || []);
    } catch (err) { setMessage(err instanceof Error ? err.message : 'Ошибка загрузки сеансов'); }
    finally { setSessionsBusy(false); }
  }

  async function revokeBrowserSession(id:string, current:boolean) {
    try {
      const response = await fetch(`${API}/api/v1/auth/session/sessions/${encodeURIComponent(id)}`, {method:'DELETE', credentials:'include', headers:csrfHeaders()});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось завершить сеанс');
      if (current || data.current_session) { setToken(''); setCompany(null); setMessage('Текущий сеанс завершён.'); return; }
      setMessage('Выбранный сеанс завершён.'); await loadBrowserSessions();
    } catch (err) { setMessage(err instanceof Error ? err.message : 'Ошибка завершения сеанса'); }
  }

  async function logout() {
    try {
      const response = await fetch(`${API}/api/v1/auth/session/logout`, {
        method:'POST', credentials:'include', headers:csrfHeaders()
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось завершить текущий сеанс');
      setToken(''); setCompany(null); setMessage('Вы вышли из системы.');
    } catch (err) {
      // Keep the authenticated UI when the server did not confirm revocation.
      setMessage(err instanceof Error ? err.message : 'Ошибка выхода из системы');
    }
  }

  async function logoutAll() {
    try {
      const response = await fetch(`${API}/api/v1/auth/session/logout-all`, {method:'POST', credentials:'include', headers:csrfHeaders()});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Не удалось завершить все сеансы');
      setMessage(`Все сеансы завершены. Отозвано: ${data.revoked_sessions}.`);
      setToken(''); setCompany(null);
    } catch (err) {
      // Do not claim logout or hide the app if the server rejected the request.
      setMessage(err instanceof Error ? err.message : 'Ошибка завершения сеансов');
    }
  }

  if (token) {
    return <main className="app-shell">
      <aside className="sidebar">
        <div className="side-brand"><div className="brandmark">П</div><div className="brand">ПОТОК <span>CRM</span></div></div>
        <div className="side-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav>
          <a className={section==='home'?'selected':''} href="#" onClick={e=>{e.preventDefault();setSection('home')}}>▦　Главная</a>
          <a className={section==='tenders'?'selected':''} href="#" onClick={e=>{e.preventDefault();setSection('tenders');loadTenders();}}>▤　Тендеры</a><a>▧　Заказы</a><a>⇄　Закупки</a>
          <a>▣　Склад</a><a className={section==='shipments'?'selected':''} href="#" onClick={e=>{e.preventDefault();setSection('shipments');loadShipments();}}>⇧　Отгрузки</a><a className={section==='delivery'?'selected':''} href="#" onClick={e=>{e.preventDefault();setSection('delivery')}}>🚚　Расчёт доставки</a><a>₽　Финансы</a>
          <a>♧　Контрагенты</a><a>▧　Документы</a><a>◷　Задачи</a><a className={section==='security'?'selected':''} href="#" onClick={e=>{e.preventDefault();setSection('security');loadBrowserSessions();}}>⚙　Безопасность</a>
        </nav>
        <button className="logout" onClick={logoutAll}>Завершить все сеансы</button>
        <button className="logout" onClick={logout}>↪　Выйти</button>
      </aside>
      <section className="workspace">
        <header className="dash-top"><div><div className="crumb">Рабочее пространство / {section==='home'?'Главная':section==='tenders'?'Тендеры':section==='shipments'?'Отгрузки':section==='security'?'Безопасность':'Логистика'}</div><h1>{section==='home'?'Панель компании':section==='tenders'?'Реестр тендеров':section==='shipments'?'Отгрузки':section==='security'?'Безопасность':'Расчёт доставки'}</h1></div><div className="user-pill"><span className="avatar">{ROLE_LABELS[currentUser?.role || '']?.[0] || '•'}</span><span>{ROLE_LABELS[currentUser?.role || ''] || 'Пользователь'}</span></div></header>
        {section==='tenders' ? <div className="delivery-page">
          <div className="welcome"><div><div className="eyebrow">ТЕНДЕРНЫЙ ОТДЕЛ</div><h2>Реестр тендеров</h2><p>Ручной учёт закупочных процедур. Данные сохраняются в базе вашей компании.</p></div><button className="secondary" onClick={loadTenders} disabled={tenderBusy}>Обновить список</button></div>
          <div className="demo-banner">Пока доступен ручной ввод. Автоматическая загрузка с электронных торговых площадок не подключена.</div>
          {tenderMessage && <div className="message delivery-notice">{tenderMessage}</div>}
          <form className="delivery-form" onSubmit={createTender}>
            <h3>Добавить тендер</h3>
            <div className="delivery-fields">
              <label>Площадка<input required maxLength={40} value={tenderForm.platform} onChange={e=>setTenderForm(v=>({...v,platform:e.target.value}))}/></label>
              <label>Номер тендера<input required maxLength={100} value={tenderForm.tender_number} onChange={e=>setTenderForm(v=>({...v,tender_number:e.target.value}))}/></label>
              <label>Заказчик<input required minLength={2} maxLength={250} value={tenderForm.customer_name} onChange={e=>setTenderForm(v=>({...v,customer_name:e.target.value}))}/></label>
              <label>Начальная цена, ₽<input required type="number" min="0" step="0.01" value={tenderForm.initial_price} onChange={e=>setTenderForm(v=>({...v,initial_price:e.target.value}))}/></label>
              <label>Срок подачи заявки<input required type="datetime-local" value={tenderForm.deadline} onChange={e=>setTenderForm(v=>({...v,deadline:e.target.value}))}/></label>
              <label>Регион поставки<input maxLength={160} value={tenderForm.delivery_region} onChange={e=>setTenderForm(v=>({...v,delivery_region:e.target.value}))}/></label>
              <label>Перспективность<select value={tenderForm.prospectivity} onChange={e=>setTenderForm(v=>({...v,prospectivity:e.target.value}))}><option value="high">Высокая</option><option value="medium">Средняя</option><option value="low">Низкая</option></select></label>
              <label>Предмет закупки<input required minLength={3} maxLength={500} value={tenderForm.subject} onChange={e=>setTenderForm(v=>({...v,subject:e.target.value}))}/></label>
            </div>
            <label>Примечание<textarea maxLength={4000} value={tenderForm.notes} onChange={e=>setTenderForm(v=>({...v,notes:e.target.value}))}/></label>
            <button className="primary delivery-submit" disabled={tenderBusy}>{tenderBusy?'Сохраняем…':'Сохранить тендер'}</button>
          </form>
          <div className="delivery-history"><h3>Тендеры компании</h3>{tenderBusy?<p>Загрузка…</p>:tenders.length===0?<p>Тендеров пока нет.</p>:tenders.map(t=><article key={t.id}><b>{t.tender_number} · {t.subject}</b><span>{t.platform} · {t.customer_name}</span><small>НМЦК: {Number(t.initial_price).toLocaleString('ru-RU',{minimumFractionDigits:2})} ₽ · Срок: {new Date(t.deadline).toLocaleString('ru-RU')}</small><small>Статус: {({new:'Новый',analysis:'Анализ',preparing:'Подготовка заявки',submitted:'Подана',won:'Выигран',lost:'Проигран',cancelled:'Отменён'} as Record<string,string>)[t.status] || t.status} · Перспективность: {t.prospectivity==='high'?'Высокая':t.prospectivity==='low'?'Низкая':'Средняя'}</small>{t.delivery_region && <small>Регион поставки: {t.delivery_region}</small>}<button type="button" className="choose-option" onClick={()=>openTenderPositions(t)}>Открыть позиции</button></article>)}</div>
          {selectedTender && <div className="delivery-page"><div className="welcome"><div><div className="eyebrow">КАРТОЧКА ТЕНДЕРА</div><h2>{selectedTender.tender_number}</h2><p>{selectedTender.subject}</p></div><button type="button" className="secondary" onClick={()=>setSelectedTender(null)}>Закрыть карточку</button></div><div className="delivery-history"><h3>Позиции закупки</h3>{tenderPositions.length===0?<p>Позиции ещё не добавлены.</p>:tenderPositions.map((p:any)=><article key={p.id}><b>{p.line_number}. {p.item_name}</b><span>{p.specification || 'Характеристики не указаны'}</span><small>Количество: {p.quantity} {p.unit} · Цена за единицу: {p.estimated_unit_price ? `${Number(p.estimated_unit_price).toLocaleString('ru-RU')} ₽` : 'не указана'}</small><small>Предварительная сумма: {p.estimated_total ? `${Number(p.estimated_total).toLocaleString('ru-RU')} ₽` : 'не рассчитана'}</small><button type="button" className="choose-option" onClick={()=>{setPricingPosition(p);setPricingPreview(null);setPricingVersions([]);setPricingForm(v=>({...v,purchase:p.estimated_unit_price || ''}));setTimeout(()=>loadPricingVersions(p.id),0);}}>Рассчитать себестоимость</button></article>)}</div>{pricingPosition && <form className="delivery-form" onSubmit={calculatePositionPricing}><h3>Калькуляция: {pricingPosition.item_name}</h3><p>Все суммы вводятся на одну единицу товара, в рублях. Налог указывается вручную.</p><div className="delivery-fields">{([['purchase','Закупочная цена'],['logistics','Логистика'],['processing','Обработка'],['packaging','Упаковка'],['tax','Налоги и сборы'],['other','Прочие расходы']] as const).map(([key,label])=><label key={key}>{label}, ₽<input required={key==='purchase'} type="number" min="0" step="0.01" value={pricingForm[key]} onChange={e=>setPricingForm(v=>({...v,[key]:e.target.value}))}/></label>)}{([['conservative_margin','Осторожная маржа, %'],['target_margin','Целевая маржа, %'],['aggressive_margin','Агрессивная маржа, %']] as const).map(([key,label])=><label key={key}>{label}<input required type="number" min="0" max="99.99" step="0.01" value={pricingForm[key]} onChange={e=>setPricingForm(v=>({...v,[key]:e.target.value}))}/></label>)}</div><button className="primary delivery-submit" disabled={pricingBusy}>{pricingBusy?'Рассчитываем…':'Рассчитать три сценария'}</button>{pricingPreview && <div className="delivery-history"><h3>Результат предварительного расчёта</h3><b>Себестоимость единицы: {Number(pricingPreview.unit_cost).toLocaleString('ru-RU')} ₽</b><p>Общая себестоимость: {Number(pricingPreview.total_cost).toLocaleString('ru-RU')} ₽</p>{Object.entries(pricingPreview.scenarios).map(([name,scenario]:[string,any])=><article key={name}><b>{name.charAt(0).toUpperCase()+name.slice(1)} сценарий</b><span>Цена за единицу: {Number(scenario.unit_sale_price).toLocaleString('ru-RU')} ₽</span><small>Цена за всё количество: {Number(scenario.total_sale_price).toLocaleString('ru-RU')} ₽ · Прибыль: {Number(scenario.total_profit).toLocaleString('ru-RU')} ₽</small><small>Маржа: {scenario.actual_margin_percent}%</small></article>)}<button type="button" className="primary" disabled={pricingSaveBusy} onClick={savePositionPricing}>{pricingSaveBusy?'Сохраняем…':'Сохранить версию расчёта'}</button><small>{pricingPreview.disclaimer} Сохранение создаёт новую неизменяемую версию.</small></div>}{pricingVersions.length>0 && <div className="delivery-history"><h3>История расчётов</h3>{pricingVersions.map((v:any)=><article key={v.id}><b>Версия №{v.version}</b><span>Себестоимость: {Number(v.result.unit_cost).toLocaleString('ru-RU')} ₽ за единицу</span><small>{new Date(v.created_at).toLocaleString('ru-RU')} · Сценарная цена: {Number(v.result.scenarios['целевой'].unit_sale_price).toLocaleString('ru-RU')} ₽</small></article>)}</div>}</form>}<form className="delivery-form" onSubmit={createTenderPosition}><h3>Добавить позицию</h3><div className="delivery-fields"><label>Наименование<input required minLength={2} maxLength={300} value={positionForm.item_name} onChange={e=>setPositionForm(v=>({...v,item_name:e.target.value}))}/></label><label>Характеристики<input maxLength={2000} value={positionForm.specification} onChange={e=>setPositionForm(v=>({...v,specification:e.target.value}))}/></label><label>Количество<input required type="number" min="0.001" step="0.001" value={positionForm.quantity} onChange={e=>setPositionForm(v=>({...v,quantity:e.target.value}))}/></label><label>Единица измерения<input required maxLength={30} value={positionForm.unit} onChange={e=>setPositionForm(v=>({...v,unit:e.target.value}))}/></label><label>Ориентировочная цена за единицу, ₽<input type="number" min="0" step="0.01" value={positionForm.estimated_unit_price} onChange={e=>setPositionForm(v=>({...v,estimated_unit_price:e.target.value}))}/></label></div><label>Примечание<textarea maxLength={1000} value={positionForm.notes} onChange={e=>setPositionForm(v=>({...v,notes:e.target.value}))}/></label><button className="primary delivery-submit" disabled={positionBusy}>{positionBusy?'Сохраняем…':'Добавить позицию'}</button></form></div>}
        </div> : section==='security' ? <div className="delivery-page"><div className="welcome"><div><div className="eyebrow">УЧЁТНАЯ ЗАПИСЬ</div><h2>Активные сеансы</h2><p>Завершайте отдельные входы, которые вам неизвестны. Токены и секреты здесь не отображаются.</p></div><button className="secondary" onClick={loadBrowserSessions} disabled={sessionsBusy}>Обновить</button></div>{message && <div className="message delivery-notice">{message}</div>}<div className="delivery-history">{sessionsBusy?<p>Загрузка…</p>:browserSessions.length===0?<p>Активных сеансов нет.</p>:browserSessions.map(item=><article key={item.id}><b>{item.device} {item.current?'· Текущее устройство':''}</b><span>Создан: {new Date(item.created_at).toLocaleString('ru-RU')}</span><small>Истекает: {new Date(item.expires_at).toLocaleString('ru-RU')}</small><small>{item.user_agent || 'Данные браузера не переданы'}</small><div><button className="choose-option" onClick={()=>revokeBrowserSession(item.id,item.current)}>Завершить этот сеанс</button></div></article>)}</div></div> : section==='shipments' ? <div className="delivery-page">
          <div className="welcome"><div><div className="eyebrow">СКЛАД И ЛОГИСТИКА</div><h2>Отгрузки и стоимость доставки</h2><p>Плановая стоимость берётся из выбранного расчёта. Фактическая вносится после доставки.</p></div><button className="secondary" onClick={loadShipments} disabled={shipmentBusy}>Обновить</button></div>
          {deliveryMessage && <div className="message delivery-notice">{deliveryMessage}</div>}
          <div className="delivery-history"><h3>Список отгрузок</h3>{shipmentBusy?<p>Загрузка…</p>:shipments.length===0?<p>Отгрузок пока нет.</p>:shipments.map(item=><article key={item.id}><b>Отгрузка {item.shipment_number}</b><span>{item.destination || 'Адрес не указан'} · {item.carrier || 'Перевозчик не указан'} · {new Date(item.shipped_at).toLocaleString('ru-RU')}</span><small>План: {item.planned_delivery_cost ?? '—'} ₽ · Факт: {item.actual_delivery_cost ?? 'не внесён'} ₽ · Статус: {item.status}</small>{item.delivery_estimate_id ? <div className="delivery-fields"><label>Фактическая стоимость, ₽<input type="number" min="0" step="0.01" value={actualCosts[item.id] ?? item.actual_delivery_cost ?? ''} onChange={e=>setActualCosts(v=>({...v,[item.id]:e.target.value}))} placeholder="Сумма по документам"/></label><div><button className="choose-option" type="button" onClick={()=>saveActualCost(item.id)}>Сохранить факт</button></div></div>:<small>Плановый расчёт к этой отгрузке не привязан.</small>}</article>)}</div>
        </div> : section==='delivery' ? <div className="delivery-page">
          <div className="welcome"><div><div className="eyebrow">ЛОГИСТИКА</div><h2>Сравнение способов доставки</h2><p>Сопоставьте предложение перевозчика с затратами собственного транспорта.</p></div></div>
          <div className="demo-banner">Расчёт предварительный. Расстояние и предложение перевозчика вводятся вручную. Это не бронирование транспорта.</div>
          <form className="delivery-form" onSubmit={calculateDelivery}>
            <div className="delivery-fields">
              <label>Откуда<input required value={origin} onChange={e=>setOrigin(e.target.value)} placeholder="Склад, город, адрес"/></label>
              <label>Куда<input required value={destination} onChange={e=>setDestination(e.target.value)} placeholder="Адрес клиента"/></label>
              <label>Расстояние в одну сторону, км<input required type="number" min="0.01" step="0.01" value={distance} onChange={e=>setDistance(e.target.value)}/></label>
              <label>Описание груза<input required value={cargo} onChange={e=>setCargo(e.target.value)} placeholder="Наименование, упаковка"/></label>
            </div>
            <h3>Транспортная компания</h3>
            <div className="delivery-fields">
              <label>Название перевозчика<input value={carrierName} onChange={e=>setCarrierName(e.target.value)} placeholder="Например, ООО Перевозчик"/></label>
              <label>Предложенная стоимость, ₽<input type="number" min="0" step="0.01" value={carrierQuote} onChange={e=>setCarrierQuote(e.target.value)} placeholder="Введите цену из КП"/></label>
            </div>
            <h3>Собственный транспорт — параметры</h3>
            <div className="delivery-fields">
              <label>Расход топлива, л/100 км<input required type="number" min="0.01" step="0.01" value={fuelUse} onChange={e=>setFuelUse(e.target.value)}/></label>
              <label>Цена топлива, ₽/л<input required type="number" min="0.01" step="0.01" value={fuelPrice} onChange={e=>setFuelPrice(e.target.value)}/></label>
              <label>Водитель, ₽ за рейс<input type="number" min="0" step="0.01" value={driverCost} onChange={e=>setDriverCost(e.target.value)}/></label>
              <label>Амортизация, ₽/км<input type="number" min="0" step="0.01" value={depreciation} onChange={e=>setDepreciation(e.target.value)}/></label>
              <label>Обслуживание, ₽/км<input type="number" min="0" step="0.01" value={maintenance} onChange={e=>setMaintenance(e.target.value)}/></label>
            </div>
            <button className="primary delivery-submit" disabled={deliveryBusy}>{deliveryBusy?'Рассчитываем…':'Рассчитать и сравнить'}</button>
          </form>
          {deliveryMessage && <div className="message delivery-notice">{deliveryMessage}</div>}
          {deliveryOptions.length>0 && <div className="delivery-results"><h3>Результаты сравнения</h3><p className="history-meta">Расчёт сохранён в истории: {deliveryEstimateId}</p><div className="delivery-cards">{deliveryOptions.map((o,i)=><article className="delivery-result" key={`${o.method}-${o.name}`}><div className="result-label">{o.method==='own_fleet'?'Собственный транспорт':'Транспортная компания'}</div><h4>{o.name}</h4><strong>{Number(o.total).toLocaleString('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2})} ₽</strong><small>{o.source==='quote'?'Стоимость из предложения перевозчика':'Расчёт по введённым параметрам'}</small>{i===0&&<b className="best-option">Наименьшая стоимость</b>}<button type="button" className="choose-option" onClick={()=>chooseDeliveryOption(i)}>{selectedDeliveryIndex===i?'Выбрано':'Выбрать вариант'}</button></article>)}</div></div>} 
          <div className="history-actions"><button type="button" className="secondary" onClick={loadDeliveryHistory}>История расчётов</button></div>
          {historyOpen && (
            <div className="delivery-history">
              <h3>Сохранённые расчёты</h3>
              {deliveryHistory.length === 0 ? (
                <p>Сохранённых расчётов пока нет.</p>
              ) : (
                deliveryHistory.map((item) => (
                  <article key={item.id}>
                    <b>{item.origin} → {item.destination}</b>
                    <span>{item.cargo_description} · {item.distance_km_one_way} км · {new Date(item.created_at).toLocaleString('ru-RU')}</span>
                    <small>
                      {item.selected_option_index === null
                        ? 'Вариант не выбран'
                        : `Выбран: ${item.options[item.selected_option_index]?.name} — ${item.options[item.selected_option_index]?.total} ₽`}
                    </small>
                    <div className="history-option-list">
                      {item.options.map((option, index) => (
                        <button
                          type="button"
                          key={`${item.id}-${index}`}
                          onClick={async () => {
                            try {
                              const response = await fetch(
                                `${API}/api/v1/transport/estimates/${item.id}/select?option_index=${index}`,
                                { method: 'POST', credentials: 'include' },
                              );
                              const data = await response.json();
                              if (!response.ok) throw new Error(data.detail || 'Ошибка выбора');
                              setDeliveryMessage('Выбор сохранён в истории. Заказ перевозчику не отправлен.');
                              await loadDeliveryHistory();
                            } catch (error) {
                              setDeliveryMessage(error instanceof Error ? error.message : 'Ошибка выбора');
                            }
                          }}
                        >
                          Выбрать: {option.name} · {Number(option.total).toLocaleString('ru-RU')} ₽
                        </button>
                      ))}
                    </div>
                  </article>
                ))
              )}
            </div>
          )}
        </div> : <>
        <div className="welcome"><div><div className="eyebrow">ОБЗОР КОМПАНИИ</div><h2>{loadingCompany ? 'Загружаем компанию…' : company?.name || 'Компания'}</h2><p>Счётчики рассчитаны по данным текущей компании.</p></div><button className="secondary" onClick={loadDashboard} disabled={dashboardBusy}>{dashboardBusy?'Обновляем…':'Обновить показатели'}</button></div>
        <div className="demo-banner">ПИЛОТ 0.25 · Счётчики показывают записи компании; финансовые суммы и прогнозы здесь не рассчитываются.</div>
        {dashboardMessage && <div className="message delivery-notice">{dashboardMessage}</div>}
        <div className="kpis">
          {[
            {label:'Открытые тендеры',value:dashboardSummary?.open_tenders, note:'Новые, в анализе, подготовке или подаче',icon:'▤'},
            {label:'Утверждённые закупки',value:dashboardSummary?.authorized_procurement_orders,note:'Заказы со статусом «утверждён»',icon:'⇄'},
            {label:'Ожидают согласования',value:dashboardSummary?.pending_approvals,note:'Запросы со статусом «ожидает решения»',icon:'◷'},
            {label:'Активные резервы',value:dashboardSummary?.active_reservations,note:'Резервы, не снятые с учёта',icon:'▣'},
          ].map(item=><article className="kpi" key={item.label}><div className="kpi-head"><span>{item.label}</span><b>{item.icon}</b></div><strong>{item.value === undefined ? '—' : item.value}</strong><small>{item.note}</small></article>)}
        </div>
        <div className="dash-grid"><article className="dash-card"><div className="card-title"><h3>О данных</h3><span>Обновление вручную</span></div><p>Показаны только счётчики по текущей компании. Суммы и прогнозы здесь не рассчитываются.</p><button className="secondary" onClick={loadDashboard} disabled={dashboardBusy}>{dashboardBusy?'Обновляем…':'Обновить данные'}</button></article></div>
        <footer className="dash-footer">ПОТОК CRM · Пилот 0.25 · Показатели из базы компании</footer>
        </>}
      </section>
    </main>;
  }

  return <main className="page">
    <header className="top"><div className="brandmark">П</div><div className="brand">ПОТОК <span>CRM</span></div><div className="top-note">Управление бизнес-процессами</div></header>
    <section className="layout">
      <div className="intro"><div className="eyebrow">ЕДИНОЕ ПРОСТРАНСТВО РАБОТЫ</div><h1>От тендера<br/>до закрытия заказа.</h1><p>Закупки, склад, поставки, финансы и команда — в одной системе.</p><div className="flow"><span>Тендер</span><i>→</i><span>Закупка</span><i>→</i><span>Склад</span><i>→</i><span>Отгрузка</span></div></div>
      <div className="panel"><div className="tabs"><button className={mode==='login'?'active':''} onClick={()=>{setMode('login');setMessage('')}}>Вход</button><button className={mode==='register'?'active':''} onClick={()=>{setMode('register');setMessage('')}}>Создать компанию</button></div>
        <h2>{mode==='login'?'С возвращением':'Регистрация компании'}</h2><p className="muted">{mode==='login'?'Войдите в рабочее пространство':'Создайте тестовое рабочее пространство'}</p>
        <form onSubmit={submit}>{mode==='register' && <label>Название компании<input required minLength={2} value={companyName} onChange={e=>setCompanyName(e.target.value)} placeholder="Например, ООО «Поток»"/></label>}
          <label>Электронная почта<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@company.ru"/></label>
          <label>Пароль<input required minLength={12} type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Не менее 12 символов"/></label>
          <button className="primary" disabled={busy}>{busy?'Подождите…':mode==='login'?'Войти':'Создать компанию'}</button></form>
        {message && <div className="message" role="status">{message}</div>}
        {mode==='register' && <p className="warning">Тестовая регистрация. Перед публичным запуском этот способ регистрации необходимо заменить защищённым процессом.</p>}
      </div>
    </section><footer>ПОТОК CRM <span>·</span> Пилот 0.1 · тестовые данные</footer>
  </main>;
}
