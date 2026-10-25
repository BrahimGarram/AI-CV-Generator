import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../auth/auth.service';

@Component({
  selector: 'app-landing',
  imports: [RouterLink],
  templateUrl: './landing.html',
  styleUrl: './landing.scss',
})
export class Landing {
  readonly auth = inject(AuthService);
  readonly year = new Date().getFullYear();

  readonly features = [
    {
      icon: 'chat',
      title: 'Une vraie conversation',
      text: "Raconte ton parcours avec tes mots, même en vrac. L'assistant comprend, pose les bonnes questions et ne redemande jamais ce que tu as déjà dit.",
    },
    {
      icon: 'spark',
      title: 'Des descriptions professionnelles',
      text: "Tes stages et projets sont reformulés avec le vocabulaire attendu par les recruteurs. Tu valides chaque proposition avant qu'elle n'entre dans ton CV.",
    },
    {
      icon: 'shield',
      title: 'Zéro information inventée',
      text: "Des garde-fous vérifient chaque donnée : aucune date, compétence ou entreprise n'apparaît si tu ne l'as pas donnée ou acceptée.",
    },
    {
      icon: 'pdf',
      title: 'Un PDF prêt à envoyer',
      text: 'Un modèle IA entraîné spécialement met ton CV en page en LaTeX, la référence de la typographie, puis le convertit en PDF élégant.',
    },
  ];

  readonly steps = [
    { title: 'Crée ton compte', text: 'Inscription gratuite en quelques secondes.' },
    { title: 'Discute avec l\'assistant', text: 'Formation, stages, projets, compétences : il t\'aide à tout formuler.' },
    { title: 'Télécharge ton CV', text: 'Aperçu instantané, PDF téléchargeable et historique de tous tes CV.' },
  ];
}
