import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { SiteFooter } from './site-footer';
import { SiteHeader } from './site-header';
import { ShoppingAssistant } from '../../features/assistant/shopping-assistant';

@Component({
  selector: 'app-public-layout',
  imports: [RouterOutlet, SiteHeader, SiteFooter, ShoppingAssistant],
  template: `<app-site-header />
    <main id="main-content"><router-outlet /></main>
    <app-site-footer />
    <app-shopping-assistant />`,
})
export class PublicLayout {}
