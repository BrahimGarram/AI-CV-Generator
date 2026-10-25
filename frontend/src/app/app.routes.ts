import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './auth/auth.guards';

export const routes: Routes = [
  {
    path: '',
    title: 'CV Studio — Crée ton CV professionnel avec l\'IA',
    loadComponent: () => import('./pages/landing/landing').then((m) => m.Landing),
  },
  {
    path: 'login',
    title: 'Connexion — CV Studio',
    canActivate: [guestGuard],
    data: { mode: 'login' },
    loadComponent: () => import('./pages/auth/auth-page').then((m) => m.AuthPage),
  },
  {
    path: 'register',
    title: 'Inscription — CV Studio',
    canActivate: [guestGuard],
    data: { mode: 'register' },
    loadComponent: () => import('./pages/auth/auth-page').then((m) => m.AuthPage),
  },
  {
    path: 'app',
    title: 'Mon espace — CV Studio',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/workspace/workspace').then((m) => m.Workspace),
  },
  { path: '**', redirectTo: '' },
];
