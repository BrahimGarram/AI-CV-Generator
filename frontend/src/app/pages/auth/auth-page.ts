import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from '../../auth/auth.service';

type Mode = 'login' | 'register';

@Component({
  selector: 'app-auth-page',
  imports: [FormsModule, RouterLink],
  templateUrl: './auth-page.html',
  styleUrl: './auth-page.scss',
})
export class AuthPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly mode = toSignal(inject(ActivatedRoute).data.pipe(map((d) => d['mode'] as Mode)), {
    initialValue: 'login' as Mode,
  });
  readonly isRegister = computed(() => this.mode() === 'register');

  readonly name = signal('');
  readonly email = signal('');
  readonly password = signal('');
  readonly showPassword = signal(false);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  /** Force du mot de passe : 0 à 4. */
  readonly strength = computed(() => {
    const p = this.password();
    let score = 0;
    if (p.length >= 8) score++;
    if (p.length >= 12) score++;
    if (/[A-Z]/.test(p) && /[a-z]/.test(p)) score++;
    if (/\d/.test(p) && /[^A-Za-z0-9]/.test(p)) score++;
    return score;
  });
  readonly strengthLabel = computed(() => ['Trop court', 'Faible', 'Correct', 'Bon', 'Excellent'][this.strength()]);

  readonly canSubmit = computed(() => {
    if (this.loading()) return false;
    const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.email().trim());
    if (this.isRegister()) return this.name().trim().length >= 2 && emailOk && this.password().length >= 8;
    return emailOk && this.password().length > 0;
  });

  submit(): void {
    if (!this.canSubmit()) return;
    this.loading.set(true);
    this.error.set(null);

    const request = this.isRegister()
      ? this.auth.register(this.name().trim(), this.email().trim(), this.password())
      : this.auth.login(this.email().trim(), this.password());

    request.subscribe({
      next: () => this.router.navigateByUrl('/app'),
      error: (err: Error) => {
        this.loading.set(false);
        this.error.set(err.message);
      },
    });
  }
}
