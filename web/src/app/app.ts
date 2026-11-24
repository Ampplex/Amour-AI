import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ProfessionalAlertComponent } from './components/professional-alert/professional-alert.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, ProfessionalAlertComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
