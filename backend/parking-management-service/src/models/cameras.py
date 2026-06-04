from src.database.base import Base
from sqlalchemy import Integer, String, Enum, Float, ForeignKey, Boolean, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship

from src.models.status.camera_status import CameraStatus


class Cameras(Base):
    __tablename__ = 'camera_table'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    rtsp_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[CameraStatus] = mapped_column(
        Enum(CameraStatus),
        default=CameraStatus.ACTIVE
    )

    position_x: Mapped[float] = mapped_column(Float, nullable=True)
    position_y: Mapped[float] = mapped_column(Float, nullable=True)

    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    monitored_spot_ids: Mapped[list] = mapped_column(JSON, default=list)
    segments_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("segments_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    parking_id: Mapped[int] = mapped_column(
        ForeignKey("parkings_table.id", ondelete="CASCADE"),
        index=True
    )

    parking: Mapped["ParkingBase"] = relationship(back_populates="cameras")
