from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from mha.engine.core import ISerializer


__all__ = ['Indoor', 'Outdoor', 'Address']


@dataclass
class Indoor(ISerializer):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pm25: Optional[float] = None
    tvoc: Optional[float] = None
    co2: Optional[float] = None
    methanal: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v
            for k, v in {
                'temperature': None if self.temperature is None else self.temperature,
                'humidity': None if self.humidity is None else self.humidity,
                'pm25': None if self.pm25 is None else self.pm25,
                'tvoc': None if self.tvoc is None else self.tvoc,
                'co2': None if self.co2 is None else self.co2,
                'methanal': None if self.methanal is None else self.methanal
            }.items()
            if v is not None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Outdoor":
        return cls(
            temperature=data.get('temperature', None),
            humidity=data.get('humidity', None),
            pm25=data.get('pm25', None),
            tvoc=data.get('tvoc', None),
            co2=data.get('co2', None),
            methanal=data.get('methanal', None)
        )



@dataclass
class Address(ISerializer):
    province: str
    city: str
    district: str
   
    def to_dict(self) -> Dict[str, str]:
        return {
            'province': self.province,
            'city': self.city,
            'district': self.district
        }
    
    @classmethod
    def from_dict(cls, content) -> "Address":
        return cls(**content)



@dataclass
class Outdoor(ISerializer):
    season: Optional[str] = None
    weather: Optional[str] = None, 
    humidity: Optional[float] = None, 
    temperature: Optional[float] = None 
    time: Optional[datetime] = None
    address: Optional[Address] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v
            for k, v in {
                'time': None if self.time is None else self.time.strftime('%Y-%m-%d %H:%M:%S'),
                'season': None if self.season is None else self.season,
                'weather': None if self.weather is None else self.weather,
                'humidity': None if self.humidity is None else self.humidity,
                'temperature': None if self.temperature is None else self.temperature,
                'address': None if self.address is None else self.address.to_dict(),
            }.items()
            if v is not None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Outdoor":
        return cls(
            time=datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S') if 'time' in data else None,
            season=data.get('season', None),
            weather=data.get('weather', None),
            humidity=data.get('humidity', None),
            temperature=data.get('temperature', None),
            address=Address.from_dict(data['address']) if 'address' in data else None,
        )

