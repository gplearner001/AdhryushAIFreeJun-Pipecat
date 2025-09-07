import React from 'react';
import { Phone, Zap } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 text-white py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4 mb-4">
          <div className="bg-white/20 p-3 rounded-xl backdrop-blur-sm">
            <Phone className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Teler Call Service</h1>
            <p className="text-blue-100 text-lg">Professional Voice Call Initiation Platform</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2 text-blue-100">
          <Zap className="w-5 h-5" />
          <span className="text-sm">Powered by Teler API • Real-time Call Management</span>
        </div>
      </div>
    </header>
  );
};