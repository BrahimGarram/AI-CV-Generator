import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { API_URL } from '../config';
import { AuthService } from './auth.service';

/** Ajoute le jeton aux appels de l'API ; si la session a expiré (401), renvoie vers la connexion. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.token();
  const isApi = req.url.startsWith(API_URL);
  const isAuthRoute = req.url.startsWith(`${API_URL}/auth/login`) || req.url.startsWith(`${API_URL}/auth/register`);

  const request = token && isApi ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(request).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && isApi && !isAuthRoute) auth.logout();
      return throwError(() => error);
    }),
  );
};
