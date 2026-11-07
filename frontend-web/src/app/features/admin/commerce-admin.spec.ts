import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../core/auth/auth.service';
import { Branch, Product } from '../../core/models/catalog.model';
import { ApiErrorService } from '../../core/services/api-error.service';
import { CatalogService } from '../../core/services/catalog.service';
import { CommerceService } from '../../core/services/commerce.service';
import { ReturnRequest, Sale } from '../../core/models/commerce.model';
import { ExportService } from '../../core/services/export.service';
import { AdminApiService } from './admin-api.service';
import { PosSalesAdmin, ReturnsAdmin, SalesHistoryAdmin, SupplierHistoryAdmin } from './commerce-admin';

const mockBranches: Branch[] = [
  { id_sucursal: 1, nombre: 'Sucursal Central', direccion: 'Av. Principal 100' },
  { id_sucursal: 2, nombre: 'Sucursal Equipetrol', direccion: 'Calle 5 Este 200' },
];

const mockProducts: Product[] = [
  {
    id_producto: 10,
    id_categoria: 1,
    categoria: 'Poleras',
    id_marca: 1,
    marca: 'Capricho Urban',
    nombre: 'Polera Oversize Basic',
    descripcion: 'Algodón 100%',
    publico_objetivo: 'HOMBRE',
    permite_vestidor: true,
    activo: true,
    precio_actual: '120.00',
    imagen_principal: null,
    variantes: [
      {
        id_variante: 101,
        id_producto: 10,
        id_talla: 2,
        talla: 'M',
        id_color: 3,
        color: 'Negro',
        codigo_hex: '#000000',
        sku: 'POL-OVR-NEG-M',
        codigo_barras: '7771234567890',
        activo: true,
        stock_disponible: 5,
      },
      {
        id_variante: 102,
        id_producto: 10,
        id_talla: 2,
        talla: 'M',
        id_color: 4,
        color: 'Blanco',
        codigo_hex: '#FFFFFF',
        sku: 'POL-OVR-BLA-M',
        codigo_barras: '7771234567891',
        activo: true,
        stock_disponible: 2,
      },
      {
        id_variante: 103,
        id_producto: 10,
        id_talla: 3,
        talla: 'L',
        id_color: 3,
        color: 'Negro',
        codigo_hex: '#000000',
        sku: 'POL-OVR-NEG-L',
        codigo_barras: '7771234567892',
        activo: true,
        stock_disponible: 0,
      },
    ],
    tallas_disponibles: ['M', 'L'],
    colores_disponibles: ['Negro', 'Blanco'],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id_producto: 20,
    id_categoria: 2,
    categoria: 'Jeans',
    id_marca: 2,
    marca: 'Denim Co',
    nombre: 'Jean Baggy Classic',
    descripcion: 'Mezclilla rígida',
    publico_objetivo: 'HOMBRE',
    permite_vestidor: true,
    activo: true,
    precio_actual: '250.00',
    imagen_principal: null,
    variantes: [
      {
        id_variante: 201,
        id_producto: 20,
        id_talla: 4,
        talla: '32',
        id_color: 5,
        color: 'Azul',
        codigo_hex: '#1E3A8A',
        sku: 'JEA-BAG-AZU-32',
        codigo_barras: '7779876543210',
        activo: true,
        stock_disponible: 3,
      },
    ],
    tallas_disponibles: ['32'],
    colores_disponibles: ['Azul'],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('PosSalesAdmin', () => {
  it('locks branch for assigned cashiers and cascades garment selection (Brand -> Model -> Size -> Color -> Add to ticket)', () => {
    const userSignal = signal({
      id_usuario: 5,
      nombres: 'Carlos',
      apellidos: 'Cajero',
      correo: 'carlos@capricho.bo',
      telefono: null,
      ci: null,
      estado: 'ACTIVO' as const,
      created_at: '2026-01-01',
      roles: ['CAJERO'],
      permisos: ['ventas.crear'],
      id_sucursal: 2,
      sucursal: 'Sucursal Equipetrol',
    });

    const catalog = {
      branches: vi.fn(() => of(mockBranches)),
      products: vi.fn(() => of({ items: mockProducts, page: 1, page_size: 100, total: 2, pages: 1 })),
    };

    const commerce = {
      createPosSale: vi.fn(() =>
        of({
          id_venta: 88,
          id_cliente: null,
          id_sucursal: 2,
          sucursal: 'Sucursal Equipetrol',
          id_empleado: 5,
          id_reserva: null,
          canal_venta: 'PRESENCIAL',
          modalidad_entrega: 'ENTREGA_DIRECTA',
          estado: 'COMPLETADA',
          subtotal: '240.00',
          costo_envio: '0.00',
          total: '240.00',
          fecha_venta: '2026-09-13 10:00',
          items: [],
        }),
      ),
    };

    TestBed.configureTestingModule({
      imports: [PosSalesAdmin],
      providers: [
        { provide: AuthService, useValue: { currentUser: userSignal.asReadonly() } },
        { provide: CatalogService, useValue: catalog },
        { provide: CommerceService, useValue: commerce },
        { provide: ApiErrorService, useValue: { message: () => 'Error' } },
      ],
    });

    const fixture = TestBed.createComponent(PosSalesAdmin);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    const element = fixture.nativeElement as HTMLElement;

    // 1. Branch verification for Cashier
    expect(component.canSelectBranch()).toBe(false);
    expect(component.assignedBranchName()).toBe('Sucursal Equipetrol');
    expect(component.selectedBranchId()).toBe(2);
    expect(element.textContent).toContain('Sucursal asignada a tu usuario');
    expect(element.textContent).toContain('Caja Asignada (Fija)');
    expect(element.querySelector('.pos-branch-admin-banner select')).toBeNull();

    // 2. Cascading Garment Selection
    // Check computed brands
    expect(component.brands()).toEqual([
      { id: 1, nombre: 'Capricho Urban' },
      { id: 2, nombre: 'Denim Co' },
    ]);

    // Step 1: Select brand 'Capricho Urban' (id: 1)
    component.onBrandChange('1');
    expect(component.selectedBrandId()).toBe(1);
    expect(component.productsForBrand().length).toBe(1);
    expect(component.productsForBrand()[0].nombre).toBe('Polera Oversize Basic');

    // Step 2: Select product (id: 10)
    component.onProductChange('10');
    expect(component.selectedProductId()).toBe(10);
    // Since only 'M' and 'L' are available:
    expect(component.availableSizes()).toEqual(['M', 'L']);

    // Step 3: Select size 'M'
    component.onSizeChange('M');
    expect(component.selectedSize()).toBe('M');
    expect(component.availableVariantsForSize().length).toBe(2); // Negro and Blanco

    // Step 4: Select variant / color (id: 101, Negro, stock: 5)
    component.onVariantChange('101');
    expect(component.selectedVariantId()).toBe(101);
    expect(component.selectedStock()).toBe(5);
    expect(component.canAddCurrentVariant()).toBe(true);

    // Step 5: Set quantity to 2
    component.quantity.set(2);
    expect(component.currentItemSubtotal()).toBe(240);

    // Add to ticket
    component.addLine();
    expect(component.lines().length).toBe(1);
    expect(component.lines()[0].variant.id_variante).toBe(101);
    expect(component.lines()[0].quantity).toBe(2);
    expect(component.estimatedTotal()).toBe(240);

    // 3. Confirm POS Cash Sale
    component.confirm();
    expect(commerce.createPosSale).toHaveBeenCalledWith({
      id_sucursal: 2,
      id_cliente: null,
      modalidad_entrega: 'ENTREGA_DIRECTA',
      registrar_efectivo: true,
      items: [{ id_variante: 101, cantidad: 2 }],
    });
    expect(component.completed()?.id_venta).toBe(88);
    expect(component.lines().length).toBe(0);
  });

  it('allows administrators to select branch and switch between branches', () => {
    const adminSignal = signal({
      id_usuario: 1,
      nombres: 'Admin',
      apellidos: 'General',
      correo: 'admin@capricho.bo',
      telefono: null,
      ci: null,
      estado: 'ACTIVO' as const,
      created_at: '2026-01-01',
      roles: ['ADMIN'],
      permisos: ['ventas.crear', 'ventas.sucursales_todas'],
      id_sucursal: null,
      sucursal: null,
    });

    const catalog = {
      branches: vi.fn(() => of(mockBranches)),
      products: vi.fn(() => of({ items: mockProducts, page: 1, page_size: 100, total: 2, pages: 1 })),
    };

    TestBed.configureTestingModule({
      imports: [PosSalesAdmin],
      providers: [
        { provide: AuthService, useValue: { currentUser: adminSignal.asReadonly() } },
        { provide: CatalogService, useValue: catalog },
        { provide: CommerceService, useValue: { createPosSale: vi.fn() } },
        { provide: ApiErrorService, useValue: { message: () => 'Error' } },
      ],
    });

    const fixture = TestBed.createComponent(PosSalesAdmin);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    const element = fixture.nativeElement as HTMLElement;

    // 1. Admin can select branch
    expect(component.canSelectBranch()).toBe(true);
    expect(element.querySelector('.pos-branch-admin-banner select')).not.toBeNull();

    // 2. Admin switches branch
    component.onBranchChange('2');
    expect(component.selectedBranchId()).toBe(2);
    expect(catalog.products).toHaveBeenCalledWith(expect.objectContaining({ sucursal: 2 }));
  });
});

const mockSales: Sale[] = [
  {
    id_venta: 101,
    id_cliente: 1,
    cliente_nombre: 'María López',
    cliente_correo: 'maria@gmail.com',
    cliente_telefono: '77123456',
    id_sucursal: 1,
    sucursal: 'Sucursal Central',
    id_empleado: 5,
    empleado_nombre: 'Carlos Cajero',
    id_reserva: null,
    canal_venta: 'PRESENCIAL',
    modalidad_entrega: 'MOSTRADOR',
    estado: 'COMPLETADA',
    subtotal: '200.00',
    costo_envio: '0.00',
    total: '200.00',
    fecha_venta: '2026-09-13T10:30:00Z',
    metodo_pago: '💵 Efectivo',
    items: [
      {
        id_detalle: 1,
        id_variante: 101,
        sku: 'POL-OVR-NEG-M',
        producto: 'Polera Oversize Basic',
        color: 'Negro',
        talla: 'M',
        cantidad: 1,
        precio_unitario: '200.00',
        subtotal: '200.00',
        stock_disponible: 5,
        activo: true,
        imagen_url: null,
      },
    ],
  },
  {
    id_venta: 102,
    id_cliente: 2,
    cliente_nombre: 'Juan Pérez',
    cliente_correo: 'juan@gmail.com',
    cliente_telefono: '70011223',
    id_sucursal: 2,
    sucursal: 'Sucursal Equipetrol',
    id_empleado: null,
    empleado_nombre: null,
    id_reserva: null,
    canal_venta: 'WEB',
    modalidad_entrega: 'DELIVERY',
    estado: 'COMPLETADA',
    subtotal: '300.00',
    costo_envio: '25.00',
    total: '325.00',
    fecha_venta: '2026-09-13T11:45:00Z',
    metodo_pago: '💳 Tarjeta (Stripe)',
    items: [
      {
        id_detalle: 2,
        id_variante: 201,
        sku: 'JEA-BAG-AZU-32',
        producto: 'Jean Baggy Classic',
        color: 'Azul',
        talla: '32',
        cantidad: 2,
        precio_unitario: '150.00',
        subtotal: '300.00',
        stock_disponible: 3,
        activo: true,
        imagen_url: null,
      },
    ],
  },
];

describe('SalesHistoryAdmin', () => {
  it('renders sales history, computes KPIs, filters by channel and toggles item review', async () => {
    const adminSignal = signal({
      id_usuario: 1,
      nombres: 'Admin',
      apellidos: 'General',
      correo: 'admin@capricho.bo',
      telefono: null,
      ci: null,
      estado: 'ACTIVO' as const,
      created_at: '2026-01-01',
      roles: ['ADMIN'],
      permisos: ['ventas.ver', 'ventas.sucursales_todas'],
      id_sucursal: null,
      sucursal: null,
    });

    const catalog = {
      branches: vi.fn(() => of(mockBranches)),
    };

    const commerce = {
      adminSales: vi.fn(() => of(mockSales)),
      saleInvoice: vi.fn(() => of(new Blob(['dummy pdf'], { type: 'application/pdf' }))),
    };

    const exportService = {
      exportSalesToPdf: vi.fn(),
      exportSalesToExcel: vi.fn().mockResolvedValue(undefined),
    };

    TestBed.configureTestingModule({
      imports: [SalesHistoryAdmin],
      providers: [
        { provide: AuthService, useValue: { currentUser: adminSignal.asReadonly() } },
        { provide: CatalogService, useValue: catalog },
        { provide: CommerceService, useValue: commerce },
        { provide: ExportService, useValue: exportService },
        { provide: ApiErrorService, useValue: { message: () => 'Error' } },
      ],
    });

    const fixture = TestBed.createComponent(SalesHistoryAdmin);
    fixture.detectChanges();
    const component = fixture.componentInstance;
    const element = fixture.nativeElement as HTMLElement;

    // 1. Initial load verification
    expect(commerce.adminSales).toHaveBeenCalled();
    expect(component.sales().length).toBe(2);
    expect(component.filteredSales().length).toBe(2);

    // 2. KPI metrics calculation
    const kpis = component.kpis();
    expect(kpis.totalCount).toBe(2);
    expect(kpis.totalAmount).toBe(525); // 200 + 325
    expect(kpis.posCount).toBe(1);
    expect(kpis.posAmount).toBe(200);
    expect(kpis.webCount).toBe(1);
    expect(kpis.webAmount).toBe(325);
    expect(kpis.avgTicket).toBe(262.5);

    // Counts badge
    expect(component.counts()).toEqual({
      todas: 2,
      presencial: 1,
      web: 1,
    });

    // 3. Channel filter: PRESENCIAL
    component.channelTab.set('PRESENCIAL');
    expect(component.filteredSales().length).toBe(1);
    expect(component.filteredSales()[0].id_venta).toBe(101);
    expect(component.filteredSales()[0].canal_venta).toBe('PRESENCIAL');

    // 4. Channel filter: WEB
    component.channelTab.set('WEB');
    expect(component.filteredSales().length).toBe(1);
    expect(component.filteredSales()[0].id_venta).toBe(102);
    expect(component.filteredSales()[0].canal_venta).toBe('WEB');

    // Reset to TODAS
    component.channelTab.set('TODAS');

    // 5. Search filter
    component.searchQuery.set('María');
    expect(component.filteredSales().length).toBe(1);
    expect(component.filteredSales()[0].cliente_nombre).toBe('María López');

    component.searchQuery.set('Stripe');
    expect(component.filteredSales().length).toBe(1);
    expect(component.filteredSales()[0].id_venta).toBe(102);

    component.searchQuery.set('');

    // 6. Expand review panel
    expect(component.isExpanded(101)).toBe(false);
    component.toggleExpanded(101);
    expect(component.isExpanded(101)).toBe(true);
    expect(component.lineUnits(mockSales[0])).toBe(1);
    expect(component.lineUnits(mockSales[1])).toBe(2);

    // Toggle back
    component.toggleExpanded(101);
    expect(component.isExpanded(101)).toBe(false);

    // 7. Invoice download trigger
    component.downloadInvoice(101);
    expect(commerce.saleInvoice).toHaveBeenCalledWith(101);

    // 8. Export PDF and Excel triggers
    component.exportPdf();
    expect(exportService.exportSalesToPdf).toHaveBeenCalled();

    await component.exportExcel();
    expect(exportService.exportSalesToExcel).toHaveBeenCalled();
  });
});

describe('ReturnsAdmin', () => {
  const mockReturns: ReturnRequest[] = [
    {
      id_devolucion: 1,
      tipo_solicitud: 'CAMBIO_TALLA',
      id_venta: 101,
      id_cliente: 1,
      cliente_nombre: 'María López',
      motivo: 'Talla no adecuada',
      estado: 'PENDIENTE',
      fecha_solicitud: '2026-09-12T10:00:00Z',
      fecha_resolucion: null,
      items: [
        {
          id_detalle_devolucion: 11,
          id_detalle_venta: 1,
          id_variante: 101,
          producto: 'Polera Oversize Basic',
          talla: 'M',
          color: 'Negro',
          cantidad: 1,
          estado_prenda: 'APTA_REINGRESO',
        },
      ],
    },
    {
      id_devolucion: 2,
      tipo_solicitud: 'DEVOLUCION',
      id_venta: 102,
      id_cliente: null,
      cliente_nombre: null,
      motivo: 'Falla en costura',
      estado: 'COMPLETADA',
      fecha_solicitud: '2026-09-11T14:00:00Z',
      fecha_resolucion: '2026-09-11T14:30:00Z',
      items: [
        {
          id_detalle_devolucion: 12,
          id_detalle_venta: 2,
          id_variante: 201,
          producto: 'Jean Baggy Classic',
          talla: '32',
          color: 'Azul',
          cantidad: 1,
          estado_prenda: 'NO_APTA',
        },
      ],
    },
  ];

  it('renders returns, computes KPIs, filters by tab, and manages counter returns', () => {
    const commerce = {
      adminReturns: vi.fn().mockReturnValue(of(mockReturns)),
      updateReturn: vi.fn().mockReturnValue(of({ ...mockReturns[0], estado: 'APROBADA' })),
      inspectSaleForReturn: vi.fn().mockReturnValue(
        of({
          id_venta: 101,
          id_cliente: null,
          cliente_nombre: 'Consumidor Final',
          id_sucursal: 1,
          sucursal: 'Sucursal Central',
          canal_venta: 'PRESENCIAL',
          modalidad_entrega: 'MOSTRADOR',
          total: '120.00',
          fecha_venta: '2026-09-13T10:00:00Z',
          es_retornable: true,
          dias_habiles_transcurridos: 0,
          dias_habiles_limite: 5,
          fecha_limite_devolucion: '2026-09-18T23:59:59Z',
          motivo_invalidez: null,
          items: [
            {
              id_detalle_venta: 1,
              id_variante: 101,
              sku: 'POL-NEG-M',
              producto: 'Polera Oversize Basic',
              talla: 'M',
              color: 'Negro',
              cantidad_vendida: 1,
              cantidad_devuelta: 0,
              cantidad_disponible: 1,
              precio_unitario: '120.00',
              imagen_url: null,
            },
          ],
        }),
      ),
      createAdminReturn: vi.fn().mockReturnValue(
        of({
          id_devolucion: 3,
          id_venta: 101,
          id_cliente: null,
          cliente_nombre: 'Consumidor Final',
          motivo: 'Cambio de talla solicitado en caja',
          estado: 'COMPLETADA',
          fecha_solicitud: '2026-09-13T12:00:00Z',
          fecha_resolucion: '2026-09-13T12:00:00Z',
          items: [],
        }),
      ),
    };

    TestBed.configureTestingModule({
      imports: [ReturnsAdmin],
      providers: [
        { provide: CatalogService, useValue: { products: vi.fn(() => of({ items: [], page: 1, pages: 1 })) } },
        { provide: CommerceService, useValue: commerce },
        { provide: ApiErrorService, useValue: { message: (_e: unknown, f: string) => f } },
      ],
    });

    const fixture = TestBed.createComponent(ReturnsAdmin);
    const component = fixture.componentInstance;
    fixture.detectChanges();

    // 1. Check data loading & KPIs
    expect(component.items().length).toBe(2);
    expect(component.kpis().total).toBe(2);
    expect(component.kpis().pending).toBe(1);
    expect(component.kpis().completed).toBe(1);

    // 2. Filter by status tab
    component.statusTab.set('PENDIENTE');
    expect(component.filteredItems().length).toBe(1);
    expect(component.filteredItems()[0].id_devolucion).toBe(1);

    component.statusTab.set('TODAS');

    // 3. Search query
    component.searchQuery.set('costura');
    expect(component.filteredItems().length).toBe(1);
    expect(component.filteredItems()[0].id_devolucion).toBe(2);
    component.searchQuery.set('');

    // 4. Update state transition
    component.update(1, 'APROBADA');
    expect(commerce.updateReturn).toHaveBeenCalledWith(1, 'APROBADA');

    // 5. Counter return modal flow
    component.openCounterReturnModal();
    expect(component.showModal()).toBe(true);

    component.searchSaleId.set(101);
    component.searchSale();
    expect(commerce.inspectSaleForReturn).toHaveBeenCalledWith(101);
    expect(component.inspectedSale()?.es_retornable).toBe(true);

    component.modalMotivo.set('Cambio de talla solicitado en caja');
    expect(component.canSubmitCounterReturn()).toBe(true);

    component.submitCounterReturn();
    expect(commerce.createAdminReturn).toHaveBeenCalled();
    expect(commerce.createAdminReturn.mock.calls[0][0].completar_inmediato).toBe(false);
    expect(component.showModal()).toBe(false);
    expect(component.items().length).toBe(3);
  });
});

describe('SupplierHistoryAdmin', () => {
  it('loads purchases, switches date presets and triggers PDF and Excel exports', async () => {
    const mockPurchases = [
      {
        id_recepcion: 1,
        id_orden_compra: 10,
        proveedor: 'Textiles La Paz',
        producto: 'Camisa Formal',
        color: 'Blanco',
        talla: 'L',
        cantidad: 5,
        precio_unitario: 120,
        subtotal: 600,
        total_compra: 600,
        sucursal: 'Central',
        usuario_responsable: 'Admin',
        fecha_recepcion: '2026-09-16T11:00:00Z',
      },
    ];

    const adminApi = {
      list: vi.fn(() => of([{ id_proveedor: 1, razon_social: 'Textiles La Paz' }])),
    };

    const catalog = {
      branches: vi.fn(() => of(mockBranches)),
    };

    const commerce = {
      supplierPurchaseHistory: vi.fn(() =>
        of({
          items: mockPurchases,
          total: 1,
          page: 1,
          page_size: 25,
        })
      ),
    };

    const exportService = {
      exportPurchasesToPdf: vi.fn(),
      exportPurchasesToExcel: vi.fn().mockResolvedValue(undefined),
    };

    TestBed.configureTestingModule({
      imports: [SupplierHistoryAdmin],
      providers: [
        { provide: AdminApiService, useValue: adminApi },
        { provide: CatalogService, useValue: catalog },
        { provide: CommerceService, useValue: commerce },
        { provide: ExportService, useValue: exportService },
        { provide: ApiErrorService, useValue: { message: () => 'Error' } },
      ],
    });

    const fixture = TestBed.createComponent(SupplierHistoryAdmin);
    fixture.detectChanges();
    const component = fixture.componentInstance;

    expect(adminApi.list).toHaveBeenCalledWith('suppliers');
    expect(catalog.branches).toHaveBeenCalled();
    expect(commerce.supplierPurchaseHistory).toHaveBeenCalled();
    expect(component.items().length).toBe(1);
    expect(component.total()).toBe(1);

    // Date presets
    component.applyPreset('HOY');
    expect(component.datePreset()).toBe('HOY');
    expect(component.form.value.fecha_desde).toBe(new Date().toISOString().slice(0, 10));

    component.applyPreset('SEMANA');
    expect(component.datePreset()).toBe('SEMANA');

    component.applyPreset('MES');
    expect(component.datePreset()).toBe('MES');

    component.applyPreset('TODOS');
    expect(component.datePreset()).toBe('TODOS');
    expect(component.form.value.fecha_desde).toBe('');

    // Export triggers
    await component.exportPdf();
    expect(exportService.exportPurchasesToPdf).toHaveBeenCalled();

    await component.exportExcel();
    expect(exportService.exportPurchasesToExcel).toHaveBeenCalled();
  });

  it('manages returns, opens inspection modal and completes with item conditions', () => {
    const mockReturns: ReturnRequest[] = [
      {
        id_devolucion: 10,
        tipo_solicitud: 'REEMBOLSO',
        id_sucursal: 1,
        id_venta: 25,
        cliente_nombre: 'Carlos Perez',
        motivo: 'Talla grande',
        estado: 'APROBADA',
        fecha_solicitud: '2026-09-18T10:00:00Z',
        fecha_resolucion: null,
        items: [
          {
            id_detalle_devolucion: 101,
            id_detalle_venta: 501,
            id_variante: 101,
            producto: 'Polera Oversize Basic',
            talla: 'M',
            color: 'Negro',
            cantidad: 1,
            estado_prenda: 'APTA_REINGRESO',
          },
        ],
      },
    ];

    const commerce = {
      adminReturns: vi.fn().mockReturnValue(of(mockReturns)),
      updateReturn: vi.fn().mockImplementation((id: number, payload: any) =>
        of({
          ...mockReturns[0],
          estado: typeof payload === 'string' ? payload : payload.estado,
        }),
      ),
      inspectSaleForReturn: vi.fn(),
      createAdminReturn: vi.fn(),
      quoteReturn: vi.fn(() => of({ tipo: 'REEMBOLSO', importe_devuelto: '120.00', importe_reemplazos: '0.00', diferencia: '-120.00', accion: 'REEMBOLSAR', monto: '120.00', items: [] })),
    };

    TestBed.configureTestingModule({
      imports: [ReturnsAdmin],
      providers: [
        { provide: CatalogService, useValue: { products: vi.fn(() => of({ items: [], page: 1, pages: 1 })) } },
        { provide: CommerceService, useValue: commerce },
        { provide: ApiErrorService, useValue: { message: () => 'Error' } },
      ],
    });

    const fixture = TestBed.createComponent(ReturnsAdmin);
    fixture.detectChanges();
    const component = fixture.componentInstance;

    expect(commerce.adminReturns).toHaveBeenCalled();
    expect(component.items().length).toBe(1);
    expect(component.kpis().approved).toBe(1);

    // Open inspection modal
    component.openInspectionModal(mockReturns[0]);
    expect(component.inspectingReturn()?.id_devolucion).toBe(10);
    expect(component.inspectionConditions()[101]).toBe('APTA_REINGRESO');

    // Change condition to NO_APTA
    component.updateInspectionCondition(101, 'NO_APTA');
    expect(component.inspectionConditions()[101]).toBe('NO_APTA');

    // Complete inspection
    component.inspectionObservations.set('Revisado con defecto');
    component.resolveInspection('COMPLETADA');
    expect(commerce.updateReturn).not.toHaveBeenCalled();
    component.receiptChecklist.set({ comprobante_verificado: true, sin_uso: true, sin_lavado: true, etiquetas_conservadas: true, sin_danos_cliente: true });
    component.quoteSettlement();
    component.settlementConfirmed.set(true);
    component.resolveInspection('COMPLETADA');

    expect(commerce.updateReturn).toHaveBeenCalledWith(10, expect.objectContaining({
      estado: 'COMPLETADA',
      items: [{ id_detalle_devolucion: 101, estado_prenda: 'NO_APTA' }],
      observaciones: 'Revisado con defecto',
      resolucion: { tipo: 'REEMBOLSO', reemplazos: [], monto_confirmado: '120.00', medio: 'EFECTIVO', referencia: null },
    }));
    expect(component.inspectingReturn()).toBeNull();
  });
});

