import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, tap, throwError } from 'rxjs';

import { API_URL } from '../config';

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
  cv_count: number;
}

interface AuthResponse {
  token: string;
  user: User;
}

const TOKEN_KEY = 'cvstudio.token';
const USER_KEY = 'cvstudio.user';

/** Compte connecté : jeton JWT et utilisateur, conservés dans le navigateur. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly token = signal<string | null>(read(TOKEN_KEY));
  readonly user = signal<User | null>(readJson<User>(USER_KEY));
  readonly isLoggedIn = computed(() => !!this.token());
  readonly firstName = computed(() => this.user()?.name.split(' ')[0] ?? '');
  readonly initials = computed(() =>
    (this.user()?.name ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0].toUpperCase())
      .join(''),
  );

  register(name: string, email: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${API_URL}/auth/register`, { name, email, password })
      .pipe(tap((res) => this.store(res)), catchError(authError));
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${API_URL}/auth/login`, { email, password })
      .pipe(tap((res) => this.store(res)), catchError(authError));
  }

  /** Rafraîchit les infos du compte (nombre de CV...). */
  refresh(): void {
    this.http.get<User>(`${API_URL}/auth/me`).subscribe({
      next: (user) => this.setUser(user),
      error: () => {},
    });
  }

  logout(redirect = true): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this.token.set(null);
    this.user.set(null);
    if (redirect) this.router.navigateByUrl('/login');
  }

  private store(res: AuthResponse): void {
    localStorage.setItem(TOKEN_KEY, res.token);
    this.token.set(res.token);
    this.setUser(res.user);
  }

  private setUser(user: User): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    this.user.set(user);
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function authError(error: HttpErrorResponse) {
  let message: string;
  if (error.status === 0) message = 'Le service est momentanément indisponible. Réessaie dans quelques instants.';
  else if (error.status >= 500) message = 'Une erreur est survenue. Réessaie dans un instant.';
  else message = (error.error && typeof error.error.detail === 'string' && error.error.detail) || 'Données invalides.';
  return throwError(() => new Error(message));
}
